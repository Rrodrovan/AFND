"""Humedad de suelo de SMAP a través de AppEEARS.

Producto: SPL4SMGP.008 (SMAP L4, 9 km, sin vacíos). Se usa el L4 y no el L3 (SPL3SMP_E) porque
es el único que entrega humedad de la ZONA DE RAÍCES, además de la superficial, y no tiene huecos
entre pasadas del satélite.

Capas (nombres verificados en el catálogo de AppEEARS):
  Geophysical_Data_sm_surface   humedad superficial (0-5 cm),   m³/m³
  Geophysical_Data_sm_rootzone  humedad de zona de raíces (0-100 cm), m³/m³
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.config import BBox
from src.ingest.appeears import AppeearsClient, find_column, find_date_column, grid_points
from src.process.aggregate import DailyMean, merge_by_date, parse_date, rows_with_data, to_float
from src.process.qa import clean_soil_moisture

PRODUCT = "SPL4SMGP.008"
LAYER_SURFACE = "Geophysical_Data_sm_surface"
LAYER_ROOTZONE = "Geophysical_Data_sm_rootzone"
COVERAGE_START = date(2015, 3, 31)
SOURCE_LABEL = "SMAP SPL4SMGP.008"


def parse_results(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convierte las filas del CSV de AppEEARS en filas diarias para `soil_moisture`.

    Si el producto trae varias lecturas por día (3-horario) o varios puntos de la rejilla,
    se promedian por fecha.
    """
    if not rows:
        return []
    fieldnames = list(rows[0].keys())
    date_col = find_date_column(fieldnames)
    surface_col = find_column(fieldnames, PRODUCT, LAYER_SURFACE)
    rootzone_col = find_column(fieldnames, PRODUCT, LAYER_ROOTZONE)

    surface, rootzone = DailyMean(), DailyMean()
    for row in rows:
        day = parse_date(row[date_col])
        surface.add(day, clean_soil_moisture(to_float(row.get(surface_col))))
        rootzone.add(day, clean_soil_moisture(to_float(row.get(rootzone_col))))

    merged = merge_by_date({"surface_m3m3": surface.means(), "rootzone_m3m3": rootzone.means()})
    return rows_with_data(merged, ("surface_m3m3", "rootzone_m3m3"))


def fetch_soil_moisture(
    client: AppeearsClient, bbox: BBox, start: date, end: date, grid: int = 3
) -> list[dict[str, Any]]:
    start, end = max(start, COVERAGE_START), min(end, date.today())
    if start > end:
        return []
    rows = client.run_point_task(
        name=f"terrashift-smap-{date.today():%Y%m%d}",
        layers=[(PRODUCT, LAYER_SURFACE), (PRODUCT, LAYER_ROOTZONE)],
        points=grid_points(bbox, grid),
        start=start,
        end=end,
    )
    return parse_results(rows)
