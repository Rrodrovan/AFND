from datetime import date

import pytest

from src.ingest.appeears import AppeearsError
from src.ingest.smap import parse_results
from tests.helpers import csv_rows

HEADER = (
    "ID,Latitude,Longitude,Date,"
    "SPL4SMGP_008_Geophysical_Data_sm_surface,SPL4SMGP_008_Geophysical_Data_sm_rootzone"
)


def test_average_over_grid_points_and_fill_values_are_ignored():
    rows = csv_rows(f"""{HEADER}
p0,13.4,-86.6,2020-06-01,0.20,0.30
p1,13.5,-86.6,2020-06-01,0.30,0.40
p2,13.6,-86.6,2020-06-01,-9999,-9999
""")
    (result,) = parse_results(rows)
    assert result["date"] == date(2020, 6, 1)
    assert result["surface_m3m3"] == pytest.approx(0.25)
    assert result["rootzone_m3m3"] == pytest.approx(0.35)


def test_three_hourly_timestamps_are_averaged_per_day():
    rows = csv_rows(f"""{HEADER}
p0,13.4,-86.6,2020-06-01T01:30:00,0.10,0.30
p0,13.4,-86.6,2020-06-01T04:30:00,0.30,0.30
p0,13.4,-86.6,2020-06-02T01:30:00,0.40,0.50
""")
    results = parse_results(rows)
    assert [r["date"] for r in results] == [date(2020, 6, 1), date(2020, 6, 2)]
    assert results[0]["surface_m3m3"] == pytest.approx(0.20)


def test_values_out_of_physical_range_are_discarded():
    rows = csv_rows(f"""{HEADER}
p0,13.4,-86.6,2020-06-01,1.5,0.3
""")
    (result,) = parse_results(rows)
    assert result["surface_m3m3"] is None
    assert result["rootzone_m3m3"] == pytest.approx(0.3)


def test_days_with_no_valid_data_are_dropped():
    rows = csv_rows(f"""{HEADER}
p0,13.4,-86.6,2020-06-01,-9999,-9999
p0,13.4,-86.6,2020-06-02,0.2,0.3
""")
    assert [r["date"] for r in parse_results(rows)] == [date(2020, 6, 2)]


def test_empty_input_gives_no_rows():
    assert parse_results([]) == []


def test_unexpected_columns_fail_with_clear_error():
    rows = csv_rows("ID,Date,otra_cosa\np0,2020-06-01,1")
    with pytest.raises(AppeearsError):
        parse_results(rows)
