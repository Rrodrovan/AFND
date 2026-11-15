import random
from datetime import date, timedelta

import pytest

from src.metrics import strategies as S
from src.metrics import waterbalance as W


def synthetic_climate(first=date(2015, 4, 1), last=date(2026, 11, 10), seed=1, dry_factor=1.0):
    """Clima con estación lluviosa de mayo a octubre y una canícula en julio-agosto."""
    rnd = random.Random(seed)
    out, d = {}, first
    while d <= last:
        base = {5: 7, 6: 9, 7: 4.5, 8: 5, 9: 9, 10: 8, 11: 2}.get(d.month, 0.5) * dry_factor
        wet = rnd.random() < (0.5 if base > 3 else 0.08)
        precip = rnd.expovariate(1 / (base * 2)) if wet else 0.0
        out[d] = W.DayClimate(d, precip, 33 + rnd.uniform(-2, 2), 22 + rnd.uniform(-1, 1))
        d += timedelta(days=1)
    return out


def test_extraterrestrial_radiation_matches_fao56_example():
    # FAO-56, ejemplo 8: 3 de septiembre (día 246), 20°S → Ra = 32,2 MJ m-2 día-1 = 13,1 mm/día
    assert W.extraterrestrial_radiation_mm(-20.0, 246) == pytest.approx(13.1, abs=0.1)


def test_et0_is_plausible_for_the_dry_corridor():
    et0 = W.et0_hargreaves(35.0, 22.0, 13.5, 75)  # marzo
    assert 4.0 < et0 < 7.5


def test_et0_never_negative_and_handles_equal_temperatures():
    assert W.et0_hargreaves(20.0, 20.0, 13.5, 100) == 0.0


def test_kc_curve_follows_the_stages():
    crop = S.CROPS["MAIZ"]
    assert W.kc_at(crop, 0) == crop.kc_ini
    assert W.kc_at(crop, 20 + 35) == crop.kc_mid           # empieza la etapa media
    assert crop.kc_ini < W.kc_at(crop, 40) < crop.kc_mid    # en desarrollo
    assert W.kc_at(crop, crop.cycle_days) == crop.kc_end
    assert W.kcb_at(crop, 0) == crop.kcb_ini


def test_relative_yield_is_bounded():
    assert W.relative_yield(0.0, 1.25) == 1.0
    assert W.relative_yield(1.0, 1.25) == 0.0
    assert W.relative_yield(0.4, 1.25) == pytest.approx(0.5)


def test_incomplete_or_gappy_seasons_are_skipped():
    clim = synthetic_climate(last=date(2026, 11, 10))
    # el ciclo del frijol de 2026 termina el 19 de diciembre: no hay datos suficientes
    assert W.simulate_season(clim, 2026, S.CROPS["FRIJOL"], S.MANAGEMENT["E1"], 13.5) is None
    assert W.simulate_season(clim, 2025, S.CROPS["FRIJOL"], S.MANAGEMENT["E1"], 13.5) is not None
    # más del 5 % de días sin dato → se descarta
    gappy = dict(clim)
    for i in range(20):
        d = date(2020, 6, 1) + timedelta(days=i)
        gappy[d] = W.DayClimate(d, None, None, None)
    assert W.simulate_season(gappy, 2020, S.CROPS["MAIZ"], S.MANAGEMENT["E1"], 13.5) is None
    # pocos huecos → se rellena y se calcula
    few = dict(clim)
    few[date(2020, 6, 1)] = W.DayClimate(date(2020, 6, 1), None, 33.0, 22.0)
    assert W.simulate_season(few, 2020, S.CROPS["MAIZ"], S.MANAGEMENT["E1"], 13.5) is not None


def test_more_rain_never_lowers_the_yield():
    wet = W.simulate_season(synthetic_climate(dry_factor=1.5), 2020, S.CROPS["MAIZ"], S.MANAGEMENT["E1"], 13.5)
    dry = W.simulate_season(synthetic_climate(dry_factor=0.5), 2020, S.CROPS["MAIZ"], S.MANAGEMENT["E1"], 13.5)
    assert wet.stress <= dry.stress
    assert wet.rain_mm > dry.rain_mm


def test_conservation_and_regeneration_never_do_worse_than_baseline_under_the_same_weather():
    clim = synthetic_climate()
    for crop in S.CROPS.values():
        for year in range(2016, 2025):
            res = {c: W.simulate_season(clim, year, crop, m, 13.5) for c, m in S.MANAGEMENT.items()}
            assert res["E2"].stress <= res["E1"].stress + 1e-9
            assert res["E3"].stress <= res["E1"].stress + 1e-9
            assert res["E2"].effective_rain_mm >= res["E1"].effective_rain_mm


def test_compute_produces_every_combination_with_ranges():
    clim = synthetic_climate()
    rows = S.compute(clim, 13.5, date(2026, 11, 10), date(2015, 4, 1))
    # 2 cultivos × 3 escenarios × 3 estrategias × 4 indicadores
    assert len(rows) == 2 * 3 * 3 * 4
    assert {r["scenario"] for r in rows} == {"normal", "seco", "canicula"}
    for r in rows:
        assert r["value_min"] <= r["value_mid"] <= r["value_max"]
        if r["unit"] == "%":
            assert 0 <= r["value_min"] and r["value_max"] <= 100


def test_dry_scenario_is_never_better_than_normal_for_the_baseline():
    rows = S.compute(synthetic_climate(), 13.5, date(2026, 11, 10), date(2015, 4, 1))
    ry = {(r["crop"], r["scenario"]): r["value_mid"] for r in rows
          if r["strategy"] == "E1" and r["indicator"].startswith("Rendimiento")}
    for crop in ("MAIZ", "FRIJOL"):
        assert ry[(crop, "seco")] <= ry[(crop, "normal")]


def test_all_strategies_share_the_same_scenario_years():
    clim = synthetic_climate()
    base = {y: W.simulate_season(clim, y, S.CROPS["MAIZ"], S.MANAGEMENT["E1"], 13.5) for y in range(2015, 2026)}
    julaug = {y: S._julaug_rain(clim, y) for y in base}
    picked = S.pick_scenario_years(base, julaug)
    assert len(picked["seco"]) == 3 and len(picked["canicula"]) == 3 and len(picked["normal"]) >= 3
    rain = sorted(base[y].rain_mm for y in base)
    assert all(base[y].rain_mm <= rain[3] for y in picked["seco"])


def test_too_short_series_computes_nothing():
    clim = synthetic_climate(first=date(2023, 4, 1), last=date(2026, 11, 10))
    assert S.compute(clim, 13.5, date(2026, 11, 10), date(2023, 4, 1)) == []
