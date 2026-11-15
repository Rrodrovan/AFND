"""Pruebas contra un PostgreSQL real. Se omiten si no se define TERRASHIFT_TEST_DSN.

Ejemplo:  TERRASHIFT_TEST_DSN="host=localhost port=55432 dbname=ts user=ts" pytest tests/test_sync_db.py
La base debe tener ya el esquema (02_schema.sql) y database/init/03_ingest_tracking.sql.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

DSN = os.environ.get("TERRASHIFT_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="TERRASHIFT_TEST_DSN no definido")

psycopg = pytest.importorskip("psycopg")

from src import sync  # noqa: E402
from src.load import postgres  # noqa: E402

TODAY = date(2026, 11, 14)
BBOX = (-86.70, 13.40, -86.50, 13.60)


@pytest.fixture()
def conn():
    with psycopg.connect(DSN) as connection:
        with connection.cursor() as cur:
            cur.execute("TRUNCATE ingest_run, climate_daily, soil_moisture, vegetation_index, zone RESTART IDENTITY CASCADE")
        connection.commit()
        yield connection


def smap_spec(conn, calls):
    def fetch(start, end):
        calls.append((start, end))
        return [
            {"date": start + timedelta(days=i), "surface_m3m3": 0.2, "rootzone_m3m3": 0.3}
            for i in range((end - start).days + 1)
        ]

    return sync.SourceSpec(
        sync.POLICIES["smap"],
        fetch,
        lambda zid, rows: postgres.upsert_soil_moisture(conn, zid, rows),
        lambda zid: postgres.latest_date(conn, zid, "smap"),
    )


def test_sync_twice_is_idempotent_and_reports_freshness(conn):
    zone_id = postgres.ensure_zone(conn, "piloto", "Piloto", BBOX)
    conn.commit()
    calls: list = []
    start = date(2026, 9, 1)

    first = sync.run_sync(conn, zone_id, [smap_spec(conn, calls)], TODAY, start, log=lambda m: None)
    assert first[0].status == "ok"
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), max(date) FROM soil_moisture")
        total, newest = cur.fetchone()
    assert newest == TODAY - timedelta(days=5)
    assert total == (newest - start).days + 1

    second = sync.run_sync(conn, zone_id, [smap_spec(conn, calls)], TODAY, start, log=lambda m: None)
    assert second[0].status == "up_to_date"

    # al día siguiente solo se pide el solape + el día nuevo, y no se duplican filas
    third = sync.run_sync(conn, zone_id, [smap_spec(conn, calls)], TODAY + timedelta(days=1), start, log=lambda m: None)
    assert third[0].status == "ok" and third[0].start == newest - timedelta(days=6)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM soil_moisture")
        assert cur.fetchone()[0] == total + 1

    with conn.cursor() as cur:
        cur.execute("SELECT status FROM ingest_run ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["ok", "up_to_date", "ok"]
        cur.execute("SELECT source, last_date, n_rows, last_run_status FROM v_data_freshness ORDER BY source")
        rows = {r[0]: r for r in cur.fetchall()}
    assert set(rows) == {"power", "smap", "modis", "landsat"}
    assert rows["smap"][1] == newest + timedelta(days=1) and rows["smap"][3] == "ok"
    assert rows["power"][1] is None and rows["power"][2] == 0 and rows["power"][3] is None


def test_failed_run_is_visible_in_freshness_view(conn):
    zone_id = postgres.ensure_zone(conn, "piloto", "Piloto", BBOX)
    conn.commit()

    def broken(start, end):
        raise RuntimeError("AppEEARS no respondió")

    spec = sync.SourceSpec(sync.POLICIES["smap"], broken, lambda z, r: 0, lambda zid: postgres.latest_date(conn, zid, "smap"))
    sync.run_sync(conn, zone_id, [spec], TODAY, date(2026, 9, 1), log=lambda m: None)
    with conn.cursor() as cur:
        cur.execute("SELECT last_run_status, last_run_error, last_sync_ok_at FROM v_data_freshness WHERE source='smap'")
        status, error, ok_at = cur.fetchone()
    assert status == "error" and "no respondió" in error and ok_at is None


def test_monthly_view_keeps_missing_variables_as_null(conn):
    zone_id = postgres.ensure_zone(conn, "piloto", "Piloto", BBOX)
    postgres.upsert_climate_daily(conn, zone_id, [
        {"date": date(2026, 10, 1), "precip_mm": 10.0, "t2m_c": 25.0},
        {"date": date(2026, 10, 2), "precip_mm": 5.0, "t2m_c": 27.0},
    ])
    postgres.upsert_soil_moisture(conn, zone_id, [{"date": date(2026, 11, 3), "surface_m3m3": 0.1, "rootzone_m3m3": 0.25}])
    postgres.upsert_vegetation_index(conn, zone_id, [{"date": date(2026, 11, 5), "source": "MODIS", "ndvi": 0.6, "evi": 0.3}])
    with conn.cursor() as cur:
        cur.execute("SELECT month, precip_mm_total, precip_days, t2m_mean_c, rootzone_m3m3_mean, ndvi_modis_mean, ndvi_landsat_mean FROM v_observed_monthly WHERE zone_code='piloto' ORDER BY month")
        oct_row, nov_row = cur.fetchall()
    assert oct_row[1] == 15.0 and oct_row[2] == 2 and oct_row[3] == 26.0 and oct_row[4] is None
    assert nov_row[1] is None and nov_row[4] == pytest.approx(0.25) and nov_row[5] == pytest.approx(0.6) and nov_row[6] is None


def test_upsert_refreshes_updated_at(conn):
    zone_id = postgres.ensure_zone(conn, "piloto", "Piloto", BBOX)
    row = {"date": date(2026, 10, 1), "surface_m3m3": 0.1, "rootzone_m3m3": 0.2}
    postgres.upsert_soil_moisture(conn, zone_id, [row])
    with conn.cursor() as cur:
        cur.execute("UPDATE soil_moisture SET updated_at = now() - interval '5 days'")
    conn.commit()
    postgres.upsert_soil_moisture(conn, zone_id, [{**row, "rootzone_m3m3": 0.22}])
    with conn.cursor() as cur:
        cur.execute("SELECT rootzone_m3m3, now() - updated_at < interval '1 minute' FROM soil_moisture")
        value, fresh = cur.fetchone()
    assert value == pytest.approx(0.22) and fresh


# -- zonas propuestas y sincronización de varias zonas ------------------------------------------


def insert_zone(conn, code, status, bbox):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO zone (code, name, geom, status, min_lon, min_lat, max_lon, max_lat) "
            "VALUES (%s, %s, 'env', %s, %s, %s, %s, %s) RETURNING id",
            (code, code, status, *bbox),
        )
        zone_id = cur.fetchone()[0]
    conn.commit()
    return zone_id


def test_only_approved_zones_with_bbox_are_listed(conn):
    insert_zone(conn, "aprobada", "approved", BBOX)
    insert_zone(conn, "pendiente", "pending", BBOX)
    insert_zone(conn, "rechazada", "rejected", BBOX)
    zones = postgres.list_approved_zones(conn)
    assert [z[1] for z in zones] == ["aprobada"]
    assert zones[0][2] == BBOX


def test_zone_status_and_bbox_constraints(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_zone(conn, "mala", "otro", BBOX)
    conn.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_zone(conn, "invertida", "pending", (-86.5, 13.6, -86.7, 13.4))
    conn.rollback()


def test_ensure_zone_stores_bbox_columns_and_stays_approved(conn):
    postgres.ensure_zone(conn, "piloto", "Piloto", BBOX)
    conn.commit()
    assert postgres.zone_bbox(conn, "piloto") == BBOX
    assert [z[1] for z in postgres.list_approved_zones(conn)] == ["piloto"]


def test_resolve_sync_zones_all_zones_merges_env_piloto_and_database(conn, capsys):
    import argparse
    from src import cli

    insert_zone(conn, "otra", "approved", (-86.3, 13.1, -86.1, 13.3))
    insert_zone(conn, "espera", "pending", BBOX)
    args = argparse.Namespace(all_zones=True, zone="piloto", dry_run=False)

    zones = cli.resolve_sync_zones(conn, args, BBOX)
    assert [z[1] for z in zones] == ["piloto", "otra"]

    # sin PILOT_ZONE_BBOX: solo lo que hay aprobado en la base
    zones = cli.resolve_sync_zones(conn, args, None)
    assert sorted(z[1] for z in zones) == ["otra", "piloto"]


def test_changed_bbox_warns_that_loaded_data_belongs_to_the_old_box(conn, capsys):
    import argparse
    from src import cli

    postgres.ensure_zone(conn, "piloto", "Piloto", BBOX)
    conn.commit()
    args = argparse.Namespace(all_zones=False, zone="piloto", dry_run=False)
    cli.resolve_sync_zones(conn, args, (-86.0, 13.0, -85.8, 13.2))
    assert "AVISO" in capsys.readouterr().out
    assert postgres.zone_bbox(conn, "piloto") == (-86.0, 13.0, -85.8, 13.2)


def test_unknown_zone_without_env_bbox_is_an_error(conn):
    import argparse
    from src import cli

    args = argparse.Namespace(all_zones=False, zone="nada", dry_run=False)
    with pytest.raises(RuntimeError, match="no existe"):
        cli.resolve_sync_zones(conn, args, None)
