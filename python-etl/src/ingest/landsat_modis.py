"""Índices de vegetación (NDVI, EVI) de MODIS y Landsat a través de AppEEARS.

MODIS  MOD13Q1.061, 250 m, cada 16 días. NDVI y EVI vienen calculados; se filtran con su capa de calidad.
Landsat HLSL30.020 (Harmonized Landsat Sentinel-2, parte Landsat), 30 m. AppEEARS entrega bandas de
        reflectancia; NDVI y EVI se calculan aquí, tras enmascarar nubes con la capa Fmask.

Capas (nombres verificados en el catálogo de AppEEARS):
  MOD13Q1.061: _250m_16_days_NDVI, _250m_16_days_EVI, _250m_16_days_VI_Quality
  HLSL30.020:  B02 (azul), B04 (rojo), B05 (infrarrojo cercano), Fmask
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.config import BBox
from src.ingest.appeears import AppeearsClient, find_column, find_date_column, grid_points
from src.process.aggregate import DailyMean, merge_by_date, parse_date, rows_with_data, to_float
from src.process.qa import (
    clean_reflectance,
    clean_vegetation_index,
    evi,
    hls_fmask_ok,
    modis_vi_quality_ok,
    ndvi,
)

MODIS_PRODUCT = "MOD13Q1.061"
MODIS_NDVI = "_250m_16_days_NDVI"
MODIS_EVI = "_250m_16_days_EVI"
MODIS_QA = "_250m_16_days_VI_Quality"
MODIS_COVERAGE_START = date(2000, 2, 18)

HLS_PRODUCT = "HLSL30.020"
HLS_BLUE, HLS_RED, HLS_NIR, HLS_FMASK = "B02", "B04", "B05", "Fmask"
HLS_COVERAGE_START = date(2013, 4, 11)


def _as_int(text: str | None) -> int | None:
    value = to_float(text)
    return None if value is None else int(value)


def _to_rows(ndvi_series: dict, evi_series: dict, source: str) -> list[dict[str, Any]]:
    merged = merge_by_date({"ndvi": ndvi_series, "evi": evi_series})
    rows = rows_with_data(merged, ("ndvi", "evi"))
    for row in rows:
        row["source"] = source
    return rows


def parse_modis_results(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Filas diarias para `vegetation_index` (source = 'MODIS'). Descarta píxeles de mala calidad."""
    if not rows:
        return []
    fieldnames = list(rows[0].keys())
    date_col = find_date_column(fieldnames)
    ndvi_col = find_column(fieldnames, MODIS_PRODUCT, MODIS_NDVI)
    evi_col = find_column(fieldnames, MODIS_PRODUCT, MODIS_EVI)
    qa_col = find_column(fieldnames, MODIS_PRODUCT, MODIS_QA)

    ndvi_acc, evi_acc = DailyMean(), DailyMean()
    for row in rows:
        qa = _as_int(row.get(qa_col))
        if qa is None or not modis_vi_quality_ok(qa):
            continue  # sin dato de calidad o con nubes: se descarta
        day = parse_date(row[date_col])
        ndvi_acc.add(day, clean_vegetation_index(to_float(row.get(ndvi_col))))
        evi_acc.add(day, clean_vegetation_index(to_float(row.get(evi_col))))
    return _to_rows(ndvi_acc.means(), evi_acc.means(), "MODIS")


def parse_landsat_results(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Filas diarias para `vegetation_index` (source = 'LANDSAT'): NDVI y EVI calculados por píxel."""
    if not rows:
        return []
    fieldnames = list(rows[0].keys())
    date_col = find_date_column(fieldnames)
    blue_col = find_column(fieldnames, HLS_PRODUCT, HLS_BLUE)
    red_col = find_column(fieldnames, HLS_PRODUCT, HLS_RED)
    nir_col = find_column(fieldnames, HLS_PRODUCT, HLS_NIR)
    mask_col = find_column(fieldnames, HLS_PRODUCT, HLS_FMASK)

    ndvi_acc, evi_acc = DailyMean(), DailyMean()
    for row in rows:
        fmask = _as_int(row.get(mask_col))
        if fmask is None or not hls_fmask_ok(fmask):
            continue  # nube, sombra o sin dato
        blue = clean_reflectance(to_float(row.get(blue_col)))
        red = clean_reflectance(to_float(row.get(red_col)))
        nir = clean_reflectance(to_float(row.get(nir_col)))
        day = parse_date(row[date_col])
        ndvi_acc.add(day, ndvi(nir, red))
        evi_acc.add(day, evi(nir, red, blue))
    return _to_rows(ndvi_acc.means(), evi_acc.means(), "LANDSAT")


def fetch_modis(
    client: AppeearsClient, bbox: BBox, start: date, end: date, grid: int = 3
) -> list[dict[str, Any]]:
    start, end = max(start, MODIS_COVERAGE_START), min(end, date.today())
    if start > end:
        return []
    rows = client.run_point_task(
        name=f"terrashift-modis-{date.today():%Y%m%d}",
        layers=[(MODIS_PRODUCT, MODIS_NDVI), (MODIS_PRODUCT, MODIS_EVI), (MODIS_PRODUCT, MODIS_QA)],
        points=grid_points(bbox, grid),
        start=start,
        end=end,
    )
    return parse_modis_results(rows)


def fetch_landsat(
    client: AppeearsClient, bbox: BBox, start: date, end: date, grid: int = 3
) -> list[dict[str, Any]]:
    start, end = max(start, HLS_COVERAGE_START), min(end, date.today())
    if start > end:
        return []
    rows = client.run_point_task(
        name=f"terrashift-landsat-{date.today():%Y%m%d}",
        layers=[
            (HLS_PRODUCT, HLS_BLUE),
            (HLS_PRODUCT, HLS_RED),
            (HLS_PRODUCT, HLS_NIR),
            (HLS_PRODUCT, HLS_FMASK),
        ],
        points=grid_points(bbox, grid),
        start=start,
        end=end,
    )
    return parse_landsat_results(rows)
