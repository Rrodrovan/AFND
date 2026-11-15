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
    """Crea o actualiza la zona (rectángulo de la caja) y devuelve su id.

    Una zona creada o actualizada por el ETL desde su configuración queda aprobada.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO zone (code, name, geom, min_lon, min_lat, max_lon, max_lat)
            VALUES (%s, %s, ST_Multi(ST_MakeEnvelope(%s, %s, %s, %s, 4326)), %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name, geom = EXCLUDED.geom,
                min_lon = EXCLUDED.min_lon, min_lat = EXCLUDED.min_lat,
                max_lon = EXCLUDED.max_lon, max_lat = EXCLUDED.max_lat
            RETURNING id
            """,
            (code, name, min_lon, min_lat, max_lon, max_lat, min_lon, min_lat, max_lon, max_lat),
        )
        return cur.fetchone()[0]


def list_approved_zones(conn: psycopg.Connection) -> list[tuple[int, str, BBox]]:
    """Zonas aprobadas con su caja: [(id, código, (min_lon, min_lat, max_lon, max_lat))]."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, code, min_lon, min_lat, max_lon, max_lat
            FROM zone
            WHERE status = 'approved' AND min_lon IS NOT NULL
            ORDER BY id
            """
        )
        return [(r[0], r[1], (r[2], r[3], r[4], r[5])) for r in cur.fetchall()]


def zone_bbox(conn: psycopg.Connection, code: str) -> BBox | None:
    with conn.cursor() as cur:
        cur.execute("SELECT min_lon, min_lat, max_lon, max_lat FROM zone WHERE code = %s AND min_lon IS NOT NULL", (code,))
        row = cur.fetchone()
    return tuple(row) if row else None


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
                source = EXCLUDED.source,
                updated_at = now()
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
                evi = EXCLUDED.evi,
                updated_at = now()
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
            {", ".join(f"{col} = EXCLUDED.{col}" for col in CLIMATE_COLUMNS)},
            updated_at = now()
    """
    with conn.cursor() as cur:
        cur.executemany(sql, payload)
    conn.commit()
    return len(payload)


# ---------------------------------------------------------------------------------------------
# Seguimiento de la sincronización (tabla ingest_run, ver database/init/03_ingest_tracking.sql)
# ---------------------------------------------------------------------------------------------

_LATEST_DATE_SQL = {
    "power": "SELECT max(date) FROM climate_daily WHERE zone_id = %s",
    "smap": "SELECT max(date) FROM soil_moisture WHERE zone_id = %s",
    "modis": "SELECT max(date) FROM vegetation_index WHERE zone_id = %s AND source = 'MODIS'",
    "landsat": "SELECT max(date) FROM vegetation_index WHERE zone_id = %s AND source = 'LANDSAT'",
}


def find_zone_id(conn: psycopg.Connection, code: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM zone WHERE code = %s", (code,))
        row = cur.fetchone()
    return row[0] if row else None


def latest_date(conn: psycopg.Connection, zone_id: int, source: str):
    """Última fecha con datos cargados para una fuente en una zona (None si no hay)."""
    with conn.cursor() as cur:
        cur.execute(_LATEST_DATE_SQL[source], (zone_id,))
        return cur.fetchone()[0]


def start_run(conn: psycopg.Connection, zone_id: int, source: str, start, end) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingest_run (zone_id, source, status, range_start, range_end)
            VALUES (%s, %s, 'running', %s, %s) RETURNING id
            """,
            (zone_id, source, start, end),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_run(
    conn: psycopg.Connection,
    run_id: int,
    status: str,
    rows_loaded: int = 0,
    last_data_date=None,
    error: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_run
               SET status = %s, rows_loaded = %s, last_data_date = %s, error = %s, finished_at = now()
             WHERE id = %s
            """,
            (status, rows_loaded, last_data_date, (error or "")[:2000] or None, run_id),
        )
    conn.commit()
