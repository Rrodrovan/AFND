from datetime import date

import pytest

from src.ingest.appeears import AppeearsClient, AppeearsError, find_column, grid_points
from tests.helpers import FakeResponse, FakeSession

BBOX = (-86.70, 13.40, -86.50, 13.60)
RESULTS_CSV = (
    "ID,Latitude,Longitude,Date,MOD13Q1_061__250m_16_days_NDVI\n"
    "p0,13.43,-86.67,2020-06-01,0.61\n"
).encode()


def make_client(handler, **kwargs):
    session = FakeSession(handler)
    client = AppeearsClient(
        "usuario", "clave", session=session, poll_seconds=5, sleep=lambda s: None, **kwargs
    )
    return client, session


# --- rejilla de puntos -----------------------------------------------------------------------


def test_grid_single_point_is_the_centroid():
    (point,) = grid_points(BBOX, 1)
    assert point["latitude"] == pytest.approx(13.5)
    assert point["longitude"] == pytest.approx(-86.6)


def test_grid_3x3_has_nine_unique_points_inside_the_box():
    points = grid_points(BBOX, 3)
    assert len(points) == 9
    assert len({p["id"] for p in points}) == 9
    assert all(13.40 < p["latitude"] < 13.60 and -86.70 < p["longitude"] < -86.50 for p in points)


def test_grid_rejects_zero():
    with pytest.raises(ValueError):
        grid_points(BBOX, 0)


# --- búsqueda de columnas --------------------------------------------------------------------


def test_find_column_exact_match_with_underscore_layer():
    cols = ["ID", "Date", "MOD13Q1_061__250m_16_days_NDVI", "MOD13Q1_061__250m_16_days_EVI"]
    assert find_column(cols, "MOD13Q1.061", "_250m_16_days_NDVI") == "MOD13Q1_061__250m_16_days_NDVI"


def test_find_column_does_not_confuse_similar_layers():
    cols = ["SPL4SMGP_008_Geophysical_Data_sm_surface", "SPL4SMGP_008_Geophysical_Data_sm_surface_wetness"]
    assert find_column(cols, "SPL4SMGP.008", "Geophysical_Data_sm_surface") == cols[0]


def test_find_column_tolerates_different_separator():
    cols = ["HLSL30_020_B04"]
    assert find_column(cols, "HLSL30.020", "B04") == "HLSL30_020_B04"
    assert find_column(["HLSL30_020__B04"], "HLSL30.020", "B04") == "HLSL30_020__B04"


def test_find_column_raises_with_useful_message_when_missing():
    with pytest.raises(AppeearsError, match="Columnas recibidas"):
        find_column(["ID", "Date"], "SPL4SMGP.008", "Geophysical_Data_sm_rootzone")


# --- flujo completo --------------------------------------------------------------------------


def happy_handler():
    state = {"status_calls": 0}

    def handler(method, url, kwargs):
        if url.endswith("/login"):
            return FakeResponse(200, {"token": "T1"})
        if url.endswith("/task") and method == "GET":
            return FakeResponse(200, [])  # no hay tareas previas que reutilizar
        if url.endswith("/task") and method == "POST":
            return FakeResponse(202, {"task_id": "abc", "status": "pending"})
        if "/status/abc" in url:
            state["status_calls"] += 1
            if state["status_calls"] < 3:
                return FakeResponse(200, {"status": "processing"})
            return FakeResponse(303, None)
        if url.endswith("/bundle/abc"):
            return FakeResponse(200, {"files": [
                {"file_id": "f0", "file_name": "request.json"},
                {"file_id": "f1", "file_name": "task-MOD13Q1-061-results.csv"},
                {"file_id": "f2", "file_name": "granule-list.txt"},
            ]})
        if url.endswith("/bundle/abc/f1"):
            return FakeResponse(200, None, RESULTS_CSV)
        raise AssertionError(f"petición inesperada: {method} {url}")

    return handler, state


def test_full_flow_returns_rows_and_sends_correct_payload():
    handler, state = happy_handler()
    client, session = make_client(handler)

    rows = client.run_point_task(
        "tarea", [("MOD13Q1.061", "_250m_16_days_NDVI")], grid_points(BBOX, 1), date(2020, 1, 1), date(2020, 1, 31)
    )

    assert rows == [{
        "ID": "p0", "Latitude": "13.43", "Longitude": "-86.67", "Date": "2020-06-01",
        "MOD13Q1_061__250m_16_days_NDVI": "0.61",
    }]
    assert state["status_calls"] == 3

    submit = next(c for c in session.calls if c[0] == "POST" and c[1].endswith("/task"))
    payload = submit[2]["json"]
    assert payload["task_type"] == "point"
    assert payload["params"]["dates"] == [{"startDate": "01-01-2020", "endDate": "01-31-2020"}]
    assert payload["params"]["layers"] == [{"product": "MOD13Q1.061", "layer": "_250m_16_days_NDVI"}]
    assert payload["params"]["coordinates"][0]["id"] == "p0"
    assert submit[2]["headers"]["Authorization"] == "Bearer T1"


def test_only_results_csv_is_downloaded():
    handler, _ = happy_handler()
    client, session = make_client(handler)
    client.run_point_task("t", [("MOD13Q1.061", "x")], grid_points(BBOX, 1), date(2020, 1, 1), date(2020, 1, 2))
    downloads = [c[1] for c in session.calls if "/bundle/abc/" in c[1]]
    assert downloads == [downloads[0]] and downloads[0].endswith("/f1")


def test_expired_token_is_renewed_once():
    state = {"logins": 0, "rejected": False}

    def handler(method, url, kwargs):
        if url.endswith("/login"):
            state["logins"] += 1
            return FakeResponse(200, {"token": f"T{state['logins']}"})
        if "/status/" in url:
            if not state["rejected"]:
                state["rejected"] = True
                return FakeResponse(403, {"message": "expired"})
            assert kwargs["headers"]["Authorization"] == "Bearer T2"
            return FakeResponse(303, None)
        raise AssertionError(url)

    client, _ = make_client(handler)
    client.wait_for_task("abc")
    assert state["logins"] == 2


def test_failed_login_explains_what_to_check():
    client, _ = make_client(lambda m, u, k: FakeResponse(401, {"message": "bad"}))
    with pytest.raises(AppeearsError, match="EARTHDATA_USERNAME"):
        client.wait_for_task("abc")


def test_task_error_is_reported():
    def handler(method, url, kwargs):
        if url.endswith("/login"):
            return FakeResponse(200, {"token": "T"})
        return FakeResponse(200, {"status": "error", "error": "fechas fuera de rango"})

    client, _ = make_client(handler)
    with pytest.raises(AppeearsError, match="fechas fuera de rango"):
        client.wait_for_task("abc")


def test_status_as_list_is_supported():
    def handler(method, url, kwargs):
        if url.endswith("/login"):
            return FakeResponse(200, {"token": "T"})
        return FakeResponse(200, [{"status": "done"}])

    client, _ = make_client(handler)
    client.wait_for_task("abc")


def test_timeout_when_task_never_finishes():
    clock = {"t": 0.0}

    def monotonic():
        clock["t"] += 100
        return clock["t"]

    def handler(method, url, kwargs):
        if url.endswith("/login"):
            return FakeResponse(200, {"token": "T"})
        return FakeResponse(200, {"status": "processing"})

    client, _ = make_client(handler, timeout_seconds=250, monotonic=monotonic)
    with pytest.raises(AppeearsError, match="tiempo de espera"):
        client.wait_for_task("abc")


def test_bundle_without_results_csv_fails_clearly():
    def handler(method, url, kwargs):
        if url.endswith("/login"):
            return FakeResponse(200, {"token": "T"})
        return FakeResponse(200, {"files": [{"file_id": "f0", "file_name": "request.json"}]})

    client, _ = make_client(handler)
    with pytest.raises(AppeearsError, match="request.json"):
        client.download_results("abc")


def test_rejected_task_shows_server_message():
    def handler(method, url, kwargs):
        if url.endswith("/login"):
            return FakeResponse(200, {"token": "T"})
        return FakeResponse(400, None, b'{"message":"layer no existe"}')

    client, _ = make_client(handler)
    with pytest.raises(AppeearsError, match="layer no existe"):
        client.submit_point_task("t", [("X.001", "y")], grid_points(BBOX, 1), date(2020, 1, 1), date(2020, 1, 2))


# --- reutilización de tareas ya enviadas -----------------------------------------------------

POINTS = [{"id": "p0", "latitude": 13.5, "longitude": -86.6}]
LAYERS = [("SPL4SMGP.008", "Geophysical_Data_sm_surface")]


def _task_detail(start="04-01-2015", end="03-31-2016"):
    return {
        "params": {
            "dates": [{"startDate": start, "endDate": end}],
            "layers": [{"product": "SPL4SMGP.008", "layer": "Geophysical_Data_sm_surface"}],
            "coordinates": [{"id": "p0", "latitude": 13.5, "longitude": -86.6, "category": "x"}],
        }
    }


def _reuse_handler(listing, detail):
    def handler(method, url, kwargs):
        if url.endswith("/login"):
            return FakeResponse(200, {"token": "t"})
        if method == "GET" and url.endswith("/task"):
            return FakeResponse(200, listing)
        if method == "GET" and "/task/" in url:
            return FakeResponse(200, detail)
        raise AssertionError(f"petición inesperada {method} {url}")
    return handler


def test_reuses_a_matching_task_instead_of_submitting():
    listing = [{"task_id": "abc", "task_name": "terrashift-smap-20261114", "status": "done", "created": "2026-11-14"}]
    client, session = make_client(_reuse_handler(listing, _task_detail()))
    found = client.find_reusable_task(
        "terrashift-smap-20261115", LAYERS, POINTS, date(2015, 4, 1), date(2016, 3, 31)
    )
    assert found == "abc"
    assert not any(m == "POST" and u.endswith("/task") for m, u, _ in session.calls)


def test_does_not_reuse_a_task_with_a_different_range_or_name_or_status():
    listing = [
        {"task_id": "a", "task_name": "terrashift-smap-20261114", "status": "done", "created": "2"},
        {"task_id": "b", "task_name": "otra-cosa-20261114", "status": "done", "created": "3"},
        {"task_id": "c", "task_name": "terrashift-smap-20261113", "status": "error", "created": "4"},
    ]
    client, _ = make_client(_reuse_handler(listing, _task_detail(end="03-31-2017")))
    assert client.find_reusable_task(
        "terrashift-smap-20261115", LAYERS, POINTS, date(2015, 4, 1), date(2016, 3, 31)
    ) is None


def test_unreadable_listing_falls_back_to_none():
    client, _ = make_client(_reuse_handler({"no": "es lista"}, {}))
    assert client.find_reusable_task(
        "terrashift-smap-20261115", LAYERS, POINTS, date(2015, 4, 1), date(2016, 3, 31)
    ) is None
