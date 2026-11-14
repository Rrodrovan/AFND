"""Cliente de Landsat / MODIS (NDVI, EVI). PENDIENTE: Fase 2 del roadmap.

Pasos previstos:
  1. Autenticarse en NASA Earthdata.
  2. Obtener los productos de índices de vegetación que cubran PILOT_ZONE_BBOX.
  3. Aplicar máscara de nubes, agregar por zona y fecha y devolver filas para `vegetation_index`
     (campo `source` = 'LANDSAT' o 'MODIS').

Confirmar en la documentación oficial el nombre y la versión exacta de cada producto antes de fijarlos.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.config import BBox


def fetch_vegetation_index(bbox: BBox, start: date, end: date) -> list[dict[str, Any]]:
    raise NotImplementedError("Ingesta de Landsat/MODIS pendiente (Fase 2 del roadmap)")
