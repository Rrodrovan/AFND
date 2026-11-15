"""Cliente mínimo de AppEEARS (NASA) para extraer series de tiempo en puntos.

AppEEARS recorta y entrega solo los píxeles pedidos, sin descargar imágenes globales.
Documentación: https://appeears.earthdatacloud.nasa.gov/api/

Flujo: login -> POST /task (tipo point) -> GET /status -> GET /bundle -> descargar los CSV de resultados.
Requiere una cuenta gratuita de NASA Earthdata (EARTHDATA_USERNAME / EARTHDATA_PASSWORD).
"""

from __future__ import annotations

import csv
import io
import time
from datetime import date
from typing import Any, Callable, Sequence

import requests

from src.config import BBox

BASE_URL = "https://appeears.earthdatacloud.nasa.gov/api"


class AppeearsError(RuntimeError):
    """Error al hablar con AppEEARS (credenciales, tarea fallida, tiempo agotado, formato inesperado)."""


def grid_points(bbox: BBox, n: int) -> list[dict[str, Any]]:
    """Rejilla de n×n puntos (centros de celdas iguales) dentro de la caja.

    Con n=1 devuelve solo el centro. Más puntos dan un valor más representativo de la zona
    que un solo píxel.
    """
    if n < 1:
        raise ValueError("La rejilla debe tener al menos 1 punto por lado")
    min_lon, min_lat, max_lon, max_lat = bbox
    points = []
    for i in range(n):
        for j in range(n):
            points.append(
                {
                    "id": f"p{i * n + j}",
                    "latitude": round(min_lat + (i + 0.5) * (max_lat - min_lat) / n, 5),
                    "longitude": round(min_lon + (j + 0.5) * (max_lon - min_lon) / n, 5),
                }
            )
    return points


def find_column(fieldnames: Sequence[str], product_version: str, layer: str) -> str:
    """Encuentra la columna del CSV de AppEEARS que corresponde a una capa.

    AppEEARS nombra las columnas como '<Producto>_<Versión>_<Capa>' (por ejemplo
    'MOD13Q1_061__250m_16_days_NDVI'). Se busca por prefijo y sufijo para tolerar
    pequeñas diferencias de formato.
    """
    prefix = product_version.replace(".", "_")
    exact = f"{prefix}_{layer}"
    if exact in fieldnames:
        return exact
    candidates = [f for f in fieldnames if f.startswith(prefix) and f.endswith(layer)]
    if len(candidates) == 1:
        return candidates[0]
    detail = "ninguna columna coincide" if not candidates else f"varias columnas coinciden: {candidates}"
    raise AppeearsError(
        f"No se pudo identificar la columna de {product_version} / {layer}: {detail}. "
        f"Columnas recibidas: {list(fieldnames)}"
    )


def find_date_column(fieldnames: Sequence[str]) -> str:
    for name in fieldnames:
        if name.strip().lower() == "date":
            return name
    raise AppeearsError(f"El CSV no tiene columna 'Date'. Columnas: {list(fieldnames)}")


class AppeearsClient:
    def __init__(
        self,
        username: str,
        password: str,
        session: Any | None = None,
        base_url: str = BASE_URL,
        poll_seconds: float = 20,
        timeout_seconds: float = 7200,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.username = username
        self.password = password
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self._sleep = sleep
        self._monotonic = monotonic
        self._token: str | None = None

    # -- autenticación y peticiones ------------------------------------------------------

    def _login(self) -> None:
        response = self.session.request(
            "POST", f"{self.base_url}/login", auth=(self.username, self.password), timeout=60
        )
        if response.status_code != 200:
            raise AppeearsError(
                f"Falló el login en AppEEARS (HTTP {response.status_code}). "
                "Revisa EARTHDATA_USERNAME y EARTHDATA_PASSWORD."
            )
        self._token = response.json()["token"]

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Petición autenticada. Si el token caducó (403), pide uno nuevo y reintenta una vez."""
        extra_headers = kwargs.pop("headers", {})
        kwargs.setdefault("timeout", 120)
        for attempt in (1, 2):
            if self._token is None:
                self._login()
            headers = {"Authorization": f"Bearer {self._token}", **extra_headers}
            response = self.session.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
            if response.status_code == 403 and attempt == 1:
                self._token = None
                continue
            return response
        return response

    # -- catálogo -------------------------------------------------------------------------

    def list_products(self) -> list[dict[str, Any]]:
        """Catálogo público de productos de AppEEARS (no requiere iniciar sesión)."""
        response = self.session.request("GET", f"{self.base_url}/product", timeout=60)
        if response.status_code != 200:
            raise AppeearsError(f"No se pudo leer el catálogo de productos (HTTP {response.status_code})")
        return response.json()

    # -- tareas ---------------------------------------------------------------------------

    def submit_point_task(
        self,
        name: str,
        layers: Sequence[tuple[str, str]],
        points: Sequence[dict[str, Any]],
        start: date,
        end: date,
    ) -> str:
        payload = {
            "task_type": "point",
            "task_name": name,
            "params": {
                "dates": [
                    {"startDate": start.strftime("%m-%d-%Y"), "endDate": end.strftime("%m-%d-%Y")}
                ],
                "layers": [{"product": product, "layer": layer} for product, layer in layers],
                "coordinates": list(points),
            },
        }
        response = self._request("POST", "/task", json=payload)
        if response.status_code not in (200, 202):
            raise AppeearsError(
                f"AppEEARS rechazó la tarea (HTTP {response.status_code}): {response.text[:400]}"
            )
        return response.json()["task_id"]

    def wait_for_task(self, task_id: str) -> None:
        """Espera a que la tarea termine. Puede tardar de minutos a horas según el rango de fechas."""
        deadline = self._monotonic() + self.timeout_seconds
        while True:
            response = self._request("GET", f"/status/{task_id}", allow_redirects=False)
            if response.status_code == 303:  # terminada: redirige a /task/{id}
                return
            if response.status_code != 200:
                raise AppeearsError(
                    f"No se pudo consultar la tarea {task_id} (HTTP {response.status_code})"
                )
            data = response.json()
            if isinstance(data, list):
                data = data[0] if data else {}
            status = data.get("status")
            if status == "done":
                return
            if status == "error":
                raise AppeearsError(f"La tarea {task_id} terminó con error: {data.get('error') or data}")
            if self._monotonic() >= deadline:
                raise AppeearsError(
                    f"Se agotó el tiempo de espera de la tarea {task_id} (estado: {status}). "
                    "Puedes aumentar --timeout-min."
                )
            self._sleep(self.poll_seconds)

    def download_results(self, task_id: str) -> list[dict[str, str]]:
        """Descarga los CSV de resultados del bundle y los devuelve como filas."""
        listing = self._request("GET", f"/bundle/{task_id}")
        if listing.status_code != 200:
            raise AppeearsError(f"No se pudo listar el bundle de {task_id} (HTTP {listing.status_code})")
        files = listing.json().get("files", [])
        wanted = [
            f for f in files
            if f.get("file_name", "").lower().endswith(".csv") and "results" in f["file_name"].lower()
        ]
        if not wanted:
            names = [f.get("file_name") for f in files]
            raise AppeearsError(f"El bundle no trae un CSV de resultados. Archivos: {names}")

        rows: list[dict[str, str]] = []
        for entry in wanted:
            # AppEEARS redirige a una URL de S3; requests sigue la redirección y no reenvía el token.
            response = self._request("GET", f"/bundle/{task_id}/{entry['file_id']}")
            if response.status_code != 200:
                raise AppeearsError(
                    f"No se pudo descargar {entry['file_name']} (HTTP {response.status_code})"
                )
            text = response.content.decode("utf-8-sig")
            rows.extend(csv.DictReader(io.StringIO(text)))
        return rows

    def run_point_task(
        self,
        name: str,
        layers: Sequence[tuple[str, str]],
        points: Sequence[dict[str, Any]],
        start: date,
        end: date,
    ) -> list[dict[str, str]]:
        task_id = self.submit_point_task(name, layers, points, start, end)
        self.wait_for_task(task_id)
        return self.download_results(task_id)


def newer_product_versions(products: Sequence[dict[str, Any]], product_and_version: str) -> list[str]:
    """Versiones más nuevas (y vigentes) del mismo producto, p. ej. 'SPL4SMGP.008' -> ['SPL4SMGP.009'].

    Solo avisa: cambiar de versión puede cambiar los nombres de las capas, así que se hace a mano.
    """
    name, _, version = product_and_version.rpartition(".")
    if not version.isdigit():
        return []
    found: list[tuple[int, str]] = []
    for item in products:
        item_name = item.get("Product")
        item_version = str(item.get("Version", ""))
        if item_name != name or not item_version.isdigit():
            continue
        if item.get("Deleted") or item.get("Available") is False:
            continue
        if int(item_version) > int(version):
            found.append((int(item_version), f"{name}.{item_version}"))
    return [label for _, label in sorted(found)]
