from __future__ import annotations

from datetime import date, timedelta

import pytest

from src import sync
from src.ingest.appeears import newer_product_versions
from src.load import postgres
from tests.helpers import FakeResponse, FakeSession
from src.ingest.appeears import AppeearsClient, AppeearsError

TODAY = date(2026, 11, 14)
DEFAULT_START = date(2015, 4, 1)


# -- plan_window ---------------------------------------------------------------------------


def test_first_run_backfills_from_default_start_to_today_minus_latency():
    window = sync.plan_window(sync.POLICIES["smap"], None, TODAY, DEFAULT_START)
    assert window == (DEFAULT_START, TODAY - timedelta(days=5))


def test_first_run_never_starts_before_product_coverage():
    window = sync.plan_window(sync.POLICIES["smap"], None, TODAY, date(2000, 1, 1))
    assert window[0] == sync.POLICIES["smap"].coverage_start


def test_next_run_restarts_overlap_days_before_last_loaded_date():
    last = date(2026, 11, 1)
    start, end = sync.plan_window(sync.POLICIES["smap"], last, TODAY, DEFAULT_START)
    assert start == last - timedelta(days=6)  # 7 días de solape contando el último
    assert end == TODAY - timedelta(days=5)


def test_up_to_date_when_no_new_data_can_exist_yet():
    # SMAP: el último dato ya llega hasta hoy - latencia
    last = TODAY - timedelta(days=5)
    assert sync.plan_window(sync.POLICIES["smap"], last, TODAY, DEFAULT_START) is None


def test_modis_waits_for_the_next_16_day_composite():
    policy = sync.POLICIES["modis"]
    end = TODAY - timedelta(days=policy.latency_days)
    assert sync.plan_window(policy, end - timedelta(days=15), TODAY, DEFAULT_START) is None
    assert sync.plan_window(policy, end - timedelta(days=16), TODAY, DEFAULT_START) is not None


def test_no_window_when_default_start_is_in_the_future():
    assert sync.plan_window(sync.POLICIES["power"], None, TODAY, date(2030, 1, 1)) is None


# -- chunk_range ---------------------------------------------------------------------------


def test_chunk_range_covers_everything_without_gaps_or_overlap():
    start, end = date(2015, 4, 1), date(2026, 11, 9)
    chunks = sync.chunk_range(start, end, 365)
    assert chunks[0][0] == start and chunks[-1][1] == end
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert next_start == prev_end + timedelta(days=1)
    assert all((e - s).days + 1 <= 365 for s, e in chunks)


def test_chunk_range_single_day():
    assert sync.chunk_range(date(2026, 1, 1), date(2026, 1, 1), 365) == [(date(2026, 1, 1), date(2026, 1, 1))]


# -- run_sync con fuentes simuladas ---------------------------------------------------------


class FakeConn:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        pass


@pytest.fixture()
def runs(monkeypatch):
    log: list[dict] = []

    def start_run(conn, zone_id, source, start, end):
        log.append({"id": len(log), "source": source, "start": start, "end": end, "status": "running"})
        return len(log) - 1

    def finish_run(conn, run_id, status, rows_loaded=0, last_data_date=None, error=None):
        log[run_id].update(status=status, rows=rows_loaded, last=last_data_date, error=error)

    monkeypatch.setattr(postgres, "start_run", start_run)
    monkeypatch.setattr(postgres, "finish_run", finish_run)
    return log


def make_spec(key, last, fetch=None):
    state = {"last": last, "calls": []}

    def default_fetch(start, end):
        state["calls"].append((start, end))
        return [{"date": end}]

    def load(zone_id, rows):
        if rows:
            state["last"] = max(r["date"] for r in rows)
        return len(rows)

    spec = sync.SourceSpec(sync.POLICIES[key], fetch or default_fetch, load, lambda zid: state["last"])
    return spec, state


def test_run_sync_loads_each_chunk_and_records_the_run(runs):
    spec, state = make_spec("smap", None)
    results = sync.run_sync(FakeConn(), 1, [spec], TODAY, DEFAULT_START, log=lambda m: None)

    assert results[0].status == "ok"
    assert len(state["calls"]) == len(sync.chunk_range(DEFAULT_START, TODAY - timedelta(days=5), 365))
    assert runs[0]["status"] == "ok" and runs[0]["last"] == TODAY - timedelta(days=5)
    assert runs[0]["rows"] == len(state["calls"])


def test_run_sync_marks_up_to_date_without_fetching(runs):
    spec, state = make_spec("smap", TODAY - timedelta(days=5))
    results = sync.run_sync(FakeConn(), 1, [spec], TODAY, DEFAULT_START, log=lambda m: None)

    assert results[0].status == "up_to_date"
    assert state["calls"] == []
    assert runs[0]["status"] == "up_to_date"


def test_one_failing_source_does_not_stop_the_others(runs):
    def broken(start, end):
        raise AppeearsError("la tarea falló")

    bad, _ = make_spec("smap", None, fetch=broken)
    good, good_state = make_spec("power", date(2026, 11, 1))
    conn = FakeConn()
    results = sync.run_sync(conn, 1, [bad, good], TODAY, DEFAULT_START, log=lambda m: None)

    assert [r.status for r in results] == ["error", "ok"]
    assert "la tarea falló" in results[0].error
    assert conn.rollbacks == 1
    assert runs[0]["status"] == "error" and "la tarea falló" in runs[0]["error"]
    assert good_state["calls"], "la fuente sana debe sincronizarse igual"


def test_progress_of_earlier_chunks_is_kept_when_a_later_chunk_fails(runs):
    calls = []

    def flaky(start, end):
        calls.append((start, end))
        if len(calls) == 3:
            raise AppeearsError("se cortó")
        return [{"date": end}]

    spec, state = make_spec("smap", None, fetch=flaky)
    results = sync.run_sync(FakeConn(), 1, [spec], TODAY, DEFAULT_START, log=lambda m: None)

    assert results[0].status == "error" and results[0].rows == 2
    assert state["last"] == calls[1][1]  # lo cargado antes del fallo quedó guardado
    assert runs[0]["rows"] == 2


def test_dry_run_neither_fetches_nor_records(runs):
    spec, state = make_spec("smap", None)
    results = sync.run_sync(FakeConn(), None, [spec], TODAY, DEFAULT_START, dry_run=True, log=lambda m: None)

    assert results[0].status == "planned" and results[0].start == DEFAULT_START
    assert state["calls"] == [] and runs == []


# -- versiones nuevas del producto SMAP -------------------------------------------------------

PRODUCTS = [
    {"Product": "SPL4SMGP", "Version": "007", "Available": True, "Deleted": False},
    {"Product": "SPL4SMGP", "Version": "008", "Available": True, "Deleted": False},
    {"Product": "SPL4SMGP", "Version": "009", "Available": True, "Deleted": False},
    {"Product": "SPL4SMGP", "Version": "010", "Available": True, "Deleted": True},
    {"Product": "SPL3SMP_E", "Version": "006", "Available": True, "Deleted": False},
]


def test_newer_product_versions_ignores_older_deleted_and_other_products():
    assert newer_product_versions(PRODUCTS, "SPL4SMGP.008") == ["SPL4SMGP.009"]


def test_no_newer_version_when_already_latest():
    assert newer_product_versions(PRODUCTS, "SPL4SMGP.009") == []


def test_list_products_reads_the_public_catalog_without_login():
    session = FakeSession(lambda m, u, k: FakeResponse(200, PRODUCTS))
    client = AppeearsClient("u", "p", session=session)
    assert client.list_products() == PRODUCTS
    assert session.calls[0][1].endswith("/product") and "headers" not in session.calls[0][2]
