from datetime import date

import pytest

from src.ingest.landsat_modis import parse_landsat_results, parse_modis_results
from tests.helpers import csv_rows

MODIS_HEADER = (
    "ID,Date,MOD13Q1_061__250m_16_days_NDVI,MOD13Q1_061__250m_16_days_EVI,"
    "MOD13Q1_061__250m_16_days_VI_Quality"
)
HLS_HEADER = "ID,Date,HLSL30_020_B02,HLSL30_020_B04,HLSL30_020_B05,HLSL30_020_Fmask"


# --- MODIS -----------------------------------------------------------------------------------


def test_modis_good_pixels_are_averaged():
    rows = csv_rows(f"""{MODIS_HEADER}
p0,2020-06-01,0.60,0.30,0
p1,2020-06-01,0.80,0.50,1
""")
    (result,) = parse_modis_results(rows)
    assert result["source"] == "MODIS"
    assert result["ndvi"] == pytest.approx(0.70)
    assert result["evi"] == pytest.approx(0.40)


def test_modis_cloudy_and_missing_quality_pixels_are_dropped():
    rows = csv_rows(f"""{MODIS_HEADER}
p0,2020-06-01,0.60,0.30,2
p1,2020-06-01,0.60,0.30,1024
p2,2020-06-01,0.60,0.30,65535
p3,2020-06-01,0.60,0.30,
p4,2020-06-17,0.50,0.25,0
""")
    results = parse_modis_results(rows)
    assert [r["date"] for r in results] == [date(2020, 6, 17)]


def test_modis_fill_value_is_not_treated_as_data():
    rows = csv_rows(f"""{MODIS_HEADER}
p0,2020-06-01,-3000,-3000,0
p1,2020-06-17,0.5,0.3,0
""")
    assert [r["date"] for r in parse_modis_results(rows)] == [date(2020, 6, 17)]


def test_modis_unscaled_values_are_scaled():
    rows = csv_rows(f"""{MODIS_HEADER}
p0,2020-06-01,5000,2500,0
""")
    (result,) = parse_modis_results(rows)
    assert result["ndvi"] == pytest.approx(0.5)
    assert result["evi"] == pytest.approx(0.25)


# --- Landsat (HLS) ---------------------------------------------------------------------------

# azul 0.05, rojo 0.08, infrarrojo 0.40 -> NDVI 0.6667, EVI 0.5316 (calculados a mano)
CLEAR = "0.05,0.08,0.40"


def test_landsat_computes_ndvi_and_evi():
    rows = csv_rows(f"""{HLS_HEADER}
p0,2020-06-01,{CLEAR},0
""")
    (result,) = parse_landsat_results(rows)
    assert result["source"] == "LANDSAT"
    assert result["ndvi"] == pytest.approx(0.32 / 0.48, rel=1e-6)
    assert result["evi"] == pytest.approx(2.5 * 0.32 / (0.40 + 6 * 0.08 - 7.5 * 0.05 + 1), rel=1e-6)


def test_landsat_masks_cloud_adjacent_and_shadow():
    rows = csv_rows(f"""{HLS_HEADER}
p0,2020-06-01,{CLEAR},2
p1,2020-06-01,{CLEAR},4
p2,2020-06-01,{CLEAR},8
p3,2020-06-01,{CLEAR},255
p4,2020-06-09,{CLEAR},0
""")
    assert [r["date"] for r in parse_landsat_results(rows)] == [date(2020, 6, 9)]


def test_landsat_water_or_aerosol_bits_do_not_mask_the_pixel():
    # bit 5 (agua) = 32 y bits de aerosol (64/128) no deben descartar el píxel
    rows = csv_rows(f"""{HLS_HEADER}
p0,2020-06-01,{CLEAR},32
p1,2020-06-09,{CLEAR},192
""")
    assert len(parse_landsat_results(rows)) == 2


def test_landsat_unscaled_reflectance_gives_same_result():
    scaled = csv_rows(f"{HLS_HEADER}\np0,2020-06-01,0.05,0.08,0.40,0")
    raw = csv_rows(f"{HLS_HEADER}\np0,2020-06-01,500,800,4000,0")
    assert parse_landsat_results(raw)[0]["ndvi"] == pytest.approx(parse_landsat_results(scaled)[0]["ndvi"])
    assert parse_landsat_results(raw)[0]["evi"] == pytest.approx(parse_landsat_results(scaled)[0]["evi"])


def test_landsat_fill_values_give_no_row():
    rows = csv_rows(f"""{HLS_HEADER}
p0,2020-06-01,-9999,-9999,-9999,0
""")
    assert parse_landsat_results(rows) == []
