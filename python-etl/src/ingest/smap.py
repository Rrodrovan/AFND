"""Cliente de SMAP (humedad de suelo). PENDIENTE: Fase 2 del roadmap.

Pasos previstos:
  1. Autenticarse en NASA Earthdata (EARTHDATA_USERNAME / EARTHDATA_PASSWORD), por ejemplo con `earthaccess`.
  2. Buscar los productos SMAP (humedad de superficie y de zona de raíces) que cubran PILOT_ZONE_BBOX.
  3. Recortar a la zona, agregar por fecha y devolver filas para la tabla `soil_moisture`.

Confirmar en la documentación oficial el nombre y la versión exacta de cada producto antes de fijarlos.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.config import BBox


def fetch_soil_moisture(bbox: BBox, start: date, end: date) -> list[dict[str, Any]]:
    raise NotImplementedError("Ingesta de SMAP pendiente (Fase 2 del roadmap)")
