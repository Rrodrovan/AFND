"""Escritura de los resultados de E1/E2/E3 en PostgreSQL. Se omite si no se define TERRASHIFT_TEST_DSN."""

from __future__ import annotations

import os
from datetime import date

import pytest

DSN = os.environ.get("TERRASHIFT_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="TERRASHIFT_TEST_DSN no definido")

psycopg = pytest.importorskip("psycopg")

from src.load import postgres  # noqa: E402
from src.metrics import strategies  # noqa: E402
from tests.test_metrics import synthetic_climate  # noqa: E402


@pytest.fixture()
def conn():
    with psycopg.connect(DSN) as c:
        yield c
        c.rollback()


def _prepare(conn):
    postgres.ensure_zone(conn, "metrics-test", "Metrics test", (-86.70, 13.40, -86.50, 13.60))
    zone_id = postgres.find_zone_id(conn, "metrics-test")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM climate_daily WHERE zone_id = %s", (zone_id,))
        cur.execute("DELETE FROM strategy_result WHERE zone_id = %s", (zone_id,))
        cur.execute("INSERT INTO crop (code, name) VALUES ('MAIZ','Maíz'),('FRIJOL','Frijol') ON CONFLICT DO NOTHING")
        cur.execute(
            "INSERT INTO strategy (code, name, focus, description) VALUES "
            "('E1','Base','x','x'),('E2','Cons','x','x'),('E3','Reg','x','x') ON CONFLICT DO NOTHING"
        )
        for d, c in synthetic_climate().items():
            cur.execute(
                "INSERT INTO climate_daily (zone_id, date, precip_mm, t2m_max_c, t2m_min_c) VALUES (%s,%s,%s,%s,%s)",
                (zone_id, d, c.precip_mm, c.tmax_c, c.tmin_c),
            )
    conn.commit()
    return zone_id


def test_metrics_are_written_and_replaced(conn):
    zone_id = _prepare(conn)
    rows = postgres.load_climate_for_metrics(conn, zone_id)
    assert rows[0]["date"] == date(2015, 4, 1)
    out = strategies.compute(strategies.climate_index(rows), 13.5, rows[-1]["date"], rows[0]["date"])
    assert postgres.replace_strategy_results(conn, zone_id, out) == 72
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM strategy_result WHERE zone_id = %s", (zone_id,))
        assert cur.fetchone()[0] == 72
        # una segunda ejecución reemplaza: no duplica ni deja datos viejos (p. ej. de prueba)
        cur.execute(
            "INSERT INTO strategy_result (zone_id, strategy_id, crop_id, scenario, indicator, value_mid) "
            "SELECT %s, (SELECT id FROM strategy WHERE code='E1'), (SELECT id FROM crop WHERE code='MAIZ'), 'normal', 'dato de prueba', 1",
            (zone_id,),
        )
    conn.commit()
    assert postgres.replace_strategy_results(conn, zone_id, out) == 72
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM strategy_result WHERE zone_id = %s", (zone_id,))
        assert cur.fetchone()[0] == 72
        cur.execute("SELECT count(*) FROM strategy_result WHERE indicator = 'dato de prueba'")
        assert cur.fetchone()[0] == 0
