from datetime import date

import pytest

from src.config import bbox_centroid, parse_bbox
from src.ingest.power import build_params, parse_response

SAMPLE = {
    "properties": {
        "parameter": {
            "PRECTOTCORR": {"20200601": 3.2, "20200602": -999.0},
            "T2M": {"20200601": 27.1, "20200602": 28.0},
            "T2M_MAX": {"20200601": 33.0, "20200602": 34.0},
            "T2M_MIN": {"20200601": 22.0, "20200602": 22.5},
            "RH2M": {"20200601": 70.0, "20200602": 65.0},
            "ALLSKY_SFC_SW_DWN": {"20200601": 20.5, "20200602": 21.0},
        }
    }
}


def test_parse_response_converts_fill_values_to_none():
    rows = parse_response(SAMPLE)
    assert [r["date"] for r in rows] == [date(2020, 6, 1), date(2020, 6, 2)]
    assert rows[0]["precip_mm"] == 3.2
    assert rows[1]["precip_mm"] is None
    assert rows[1]["t2m_c"] == 28.0


def test_parse_response_rejects_unexpected_payload():
    with pytest.raises(ValueError):
        parse_response({"error": "x"})


def test_build_params_formats_dates_and_coordinates():
    params = build_params(13.5, -86.6, date(2020, 1, 1), date(2020, 12, 31))
    assert params["start"] == "20200101"
    assert params["end"] == "20201231"
    assert params["community"] == "AG"
    assert params["latitude"] == "13.5000"


def test_parse_bbox_and_centroid():
    bbox = parse_bbox("-86.70,13.40,-86.50,13.60")
    lat, lon = bbox_centroid(bbox)
    assert lat == pytest.approx(13.5)
    assert lon == pytest.approx(-86.6)


@pytest.mark.parametrize("bad", ["1,2,3", "a,b,c,d", "10,10,5,5", "-200,0,10,10"])
def test_parse_bbox_rejects_invalid_values(bad):
    with pytest.raises(ValueError):
        parse_bbox(bad)
