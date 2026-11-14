"""Cliente de NASA POWER (serie diaria en un punto, comunidad AG).

Documentación: https://power.larc.nasa.gov/docs/services/api/
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# Parámetro de POWER -> columna de la tabla `climate_daily`
PARAMETERS: dict[str, str] = {
    "PRECTOTCORR": "precip_mm",
    "T2M": "t2m_c",
    "T2M_MAX": "t2m_max_c",
    "T2M_MIN": "t2m_min_c",
    "RH2M": "rh2m_pct",
    "ALLSKY_SFC_SW_DWN": "solar_mj_m2",
}

# POWER marca los datos faltantes con este valor.
FILL_VALUE = -999.0


def build_params(lat: float, lon: float, start: date, end: date) -> dict[str, str]:
    return {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }


def parse_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convierte la respuesta JSON de POWER en filas para `climate_daily`.

    Los valores faltantes (-999) se devuelven como None.
    """
    try:
        series = payload["properties"]["parameter"]
    except KeyError as exc:
        raise ValueError("Respuesta de NASA POWER con formato inesperado") from exc

    days = sorted({day for values in series.values() for day in values})
    rows: list[dict[str, Any]] = []
    for day in days:
        row: dict[str, Any] = {"date": datetime.strptime(day, "%Y%m%d").date()}
        for power_name, column in PARAMETERS.items():
            value = series.get(power_name, {}).get(day)
            row[column] = None if value is None or value == FILL_VALUE else float(value)
        rows.append(row)
    return rows


def fetch_daily(
    lat: float,
    lon: float,
    start: date,
    end: date,
    session: requests.Session | None = None,
    timeout: int = 120,
) -> list[dict[str, Any]]:
    """Descarga la serie diaria de NASA POWER para un punto."""
    http = session or requests.Session()
    response = http.get(POWER_URL, params=build_params(lat, lon, start, end), timeout=timeout)
    response.raise_for_status()
    return parse_response(response.json())
