from datetime import date

import pytest

from src.cli import build_parser, expand_sources
from src.process.aggregate import DailyMean, merge_by_date, parse_date, to_float
from src.process.qa import evi, hls_fmask_ok, modis_vi_quality_ok, ndvi


def test_modis_quality_bits():
    assert modis_vi_quality_ok(0)
    assert modis_vi_quality_ok(1)
    assert not modis_vi_quality_ok(2)  # probablemente nublado
    assert not modis_vi_quality_ok(3)  # no producido
    assert not modis_vi_quality_ok(1 << 10)  # nubes mezcladas
    assert modis_vi_quality_ok(1 << 14)  # posible nieve/hielo: no se descarta aquí


def test_hls_fmask_bits():
    assert hls_fmask_ok(0)
    assert not hls_fmask_ok(2)  # nube
    assert not hls_fmask_ok(4)  # adyacente
    assert not hls_fmask_ok(8)  # sombra
    assert hls_fmask_ok(32)  # agua
    assert not hls_fmask_ok(255)  # relleno


def test_index_formulas_handle_division_by_zero():
    assert ndvi(0.0, 0.0) is None
    assert ndvi(None, 0.1) is None
    assert evi(0.4, 0.1, None) is None


def test_to_float_and_parse_date():
    assert to_float("0.5") == 0.5
    assert to_float("") is None
    assert to_float("nan") is None
    assert to_float("abc") is None
    assert to_float(None) is None
    assert parse_date("2020-06-01T01:30:00") == date(2020, 6, 1)


def test_daily_mean_and_merge():
    acc = DailyMean()
    acc.add(date(2020, 6, 1), 1.0)
    acc.add(date(2020, 6, 1), 3.0)
    acc.add(date(2020, 6, 1), None)
    assert acc.means() == {date(2020, 6, 1): 2.0}
    merged = merge_by_date({"a": {date(2020, 6, 1): 1}, "b": {date(2020, 6, 2): 2}})
    assert merged == [
        {"date": date(2020, 6, 1), "a": 1, "b": None},
        {"date": date(2020, 6, 2), "a": None, "b": 2},
    ]


def test_expand_sources():
    assert expand_sources("all") == ["power", "smap", "modis", "landsat"]
    assert expand_sources("landsat-modis") == ["modis", "landsat"]
    assert expand_sources("smap") == ["smap"]


def test_cli_defaults():
    args = build_parser().parse_args(["ingest"])
    assert (args.source, args.grid, args.timeout_min, args.zone) == ("all", 3, 360, "piloto")


def test_cli_rejects_unknown_source():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ingest", "--source", "otra"])
