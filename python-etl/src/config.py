"""Configuración del ETL a partir de variables de entorno (ver `.env.example`)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

BBox = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat


def parse_bbox(text: str) -> BBox:
    """Convierte 'min_lon,min_lat,max_lon,max_lat' en una tupla validada."""
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in text.split(","))
    except ValueError as exc:
        raise ValueError(
            "PILOT_ZONE_BBOX debe tener el formato 'min_lon,min_lat,max_lon,max_lat'"
        ) from exc
    if not (min_lon < max_lon and min_lat < max_lat):
        raise ValueError("PILOT_ZONE_BBOX: los mínimos deben ser menores que los máximos")
    if not (-180 <= min_lon and max_lon <= 180 and -90 <= min_lat and max_lat <= 90):
        raise ValueError("PILOT_ZONE_BBOX: coordenadas fuera de rango")
    return min_lon, min_lat, max_lon, max_lat


def bbox_centroid(bbox: BBox) -> tuple[float, float]:
    """Devuelve (lat, lon) del centro de la caja."""
    min_lon, min_lat, max_lon, max_lat = bbox
    return (min_lat + max_lat) / 2, (min_lon + max_lon) / 2


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def load_db_config() -> DbConfig:
    return DbConfig(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "terrashift"),
        user=os.environ.get("POSTGRES_USER", "terrashift"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )


def load_earthdata_credentials() -> tuple[str, str]:
    user = os.environ.get("EARTHDATA_USERNAME", "").strip()
    password = os.environ.get("EARTHDATA_PASSWORD", "")
    if not user or not password:
        raise RuntimeError(
            "Faltan EARTHDATA_USERNAME y EARTHDATA_PASSWORD. "
            "Crea una cuenta gratuita en https://urs.earthdata.nasa.gov y defínelas en el entorno."
        )
    return user, password


def load_pilot_bbox() -> BBox:
    raw = os.environ.get("PILOT_ZONE_BBOX")
    if not raw:
        raise RuntimeError("Define PILOT_ZONE_BBOX en el archivo .env")
    return parse_bbox(raw)


def load_date_range() -> tuple[date, date]:
    start = date.fromisoformat(os.environ.get("ETL_START_DATE", "2015-04-01"))
    end = date.fromisoformat(os.environ.get("ETL_END_DATE", "2025-12-31"))
    if start > end:
        raise ValueError("ETL_START_DATE no puede ser posterior a ETL_END_DATE")
    return start, end
