"""Acceso a PostgreSQL/PostGIS. Todas las cargas son idempotentes (UPSERT)."""

from __future__ import annotations

from typing import Any, Iterable

import psycopg

from src.config import BBox, load_db_config

CLIMATE_COLUMNS = ("precip_mm", "t2m_c", "t2m_max_c", "t2m_min_c", "rh2m_pct", "solar_mj_m2")


def connect() -> psycopg.Connection:
    cfg = load_db_config()
    return psycopg.connect(
        host=cfg.host, port=cfg.port, dbname=cfg.dbname, user=cfg.user, password=cfg.password
    )


def ensure_zone(conn: psycopg.Connection, code: str, name: str, bbox: BBox) -> int:
    """Crea o actualiza la zona (rectángulo de la caja) y devuelve su id."""
    min_lon, min_lat, max_lon, max_lat = bbox
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO zone (code, name, geom)
            VALUES (%s, %s, ST_Multi(ST_MakeEnvelope(%s, %s, %s, %s, 4326)))
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, geom = EXCLUDED.geom
            RETURNING id
            """,
            (code, name, min_lon, min_lat, max_lon, max_lat),
        )
        return cur.fetchone()[0]


SOIL_MOISTURE_SOURCE = "SMAP SPL4SMGP.008"


def upsert_soil_moisture(
    conn: psycopg.Connection, zone_id: int, rows: Iterable[dict[str, Any]]
) -> int:
    """Inserta o actualiza filas de `soil_moisture`. Devuelve cuántas filas se procesaron."""
    payload = [
        (zone_id, r["date"], r.get("surface_m3m3"), r.get("rootzone_m3m3"), SOIL_MOISTURE_SOURCE)
        for r in rows
    ]
    if not payload:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO soil_moisture (zone_id, date, surface_m3m3, rootzone_m3m3, source)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (zone_id, date) DO UPDATE SET
                surface_m3m3 = EXCLUDED.surface_m3m3,
                rootzone_m3m3 = EXCLUDED.rootzone_m3m3,
                source = EXCLUDED.source
            """,
            payload,
        )
    conn.commit()
    return len(payload)


def upsert_vegetation_index(
    conn: psycopg.Connection, zone_id: int, rows: Iterable[dict[str, Any]]
) -> int:
    """Inserta o actualiza filas de `vegetation_index` (source: 'MODIS' o 'LANDSAT')."""
    payload = [(zone_id, r["date"], r["source"], r.get("ndvi"), r.get("evi")) for r in rows]
    if not payload:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO vegetation_index (zone_id, date, source, ndvi, evi)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (zone_id, date, source) DO UPDATE SET
                ndvi = EXCLUDED.ndvi,
                evi = EXCLUDED.evi
            """,
            payload,
        )
    conn.commit()
    return len(payload)


def upsert_climate_daily(
    conn: psycopg.Connection, zone_id: int, rows: Iterable[dict[str, Any]]
) -> int:
    """Inserta o actualiza filas de `climate_daily`. Devuelve cuántas filas se procesaron."""
    payload = [
        (zone_id, row["date"], *(row.get(col) for col in CLIMATE_COLUMNS)) for row in rows
    ]
    if not payload:
        return 0
    sql = f"""
        INSERT INTO climate_daily (zone_id, date, {", ".join(CLIMATE_COLUMNS)})
        VALUES (%s, %s, {", ".join(["%s"] * len(CLIMATE_COLUMNS))})
        ON CONFLICT (zone_id, date) DO UPDATE SET
            {", ".join(f"{col} = EXCLUDED.{col}" for col in CLIMATE_COLUMNS)}
    """
    with conn.cursor() as cur:
        cur.executemany(sql, payload)
    conn.commit()
    return len(payload)
