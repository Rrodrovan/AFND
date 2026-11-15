"""Comparación de las estrategias E1, E2 y E3 con la serie observada de NASA POWER.

Las tres estrategias reciben **la misma lluvia y temperatura observadas** y solo cambian en su manejo:

  E1 · Línea base tradicional: escorrentía normal, suelo descubierto al inicio, capacidad de agua del suelo base.
  E2 · Conservación hídrica: cobertura y obras que reducen la escorrentía y la evaporación del suelo.
  E3 · Regeneración de suelos: más materia orgánica, que aumenta el agua que el suelo puede almacenar.

Los valores de `MANAGEMENT` son **supuestos del modelo**, no resultados medidos en campo; están a la vista
y se pueden ajustar para ver cómo cambian los resultados (análisis de sensibilidad).

Escenarios, definidos con los años observados (no con proyecciones):
  seco      → los 3 años con menos lluvia en el ciclo del cultivo
  canicula  → los 3 años con menos lluvia en julio-agosto
  normal    → los años intermedios por lluvia del ciclo (tercio central)
Para cada escenario se reporta la media y el rango [mín – máx] de los años que lo forman.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any, Iterable, Sequence

from src.metrics.waterbalance import (
    Crop,
    DayClimate,
    Management,
    SeasonResult,
    relative_yield,
    simulate_season,
)

# FAO-56 (Allen et al., 1998): Kc y duración de etapas (tabla 12), Kcb (tabla 17), fracción agotable p (tabla 22).
# FAO-33 (Doorenbos y Kassam, 1979): sensibilidad Ky. Fechas de siembra típicas de primera y postrera.
# El agua útil (TAW) supone un suelo franco genérico (0,15 m³/m³) y la profundidad de raíces del cultivo.
CROPS: dict[str, Crop] = {
    "MAIZ": Crop("MAIZ", 5, 15, (20, 35, 40, 30), 0.30, 1.20, 0.60, 0.15, 1.15, 0.50, 1.25, 0.55, 120.0),
    "FRIJOL": Crop("FRIJOL", 9, 1, (20, 30, 40, 20), 0.40, 1.15, 0.35, 0.15, 1.10, 0.25, 1.15, 0.45, 90.0),
}

MANAGEMENT: dict[str, Management] = {
    "E1": Management(runoff=0.15, evap_factor=1.00, taw_mult=1.00),
    "E2": Management(runoff=0.08, evap_factor=0.85, taw_mult=1.00),
    "E3": Management(runoff=0.12, evap_factor=1.00, taw_mult=1.10),
}

SCENARIOS = ("normal", "seco", "canicula")
GROUP = 3  # años que forman los escenarios seco y canícula

INDICATORS: tuple[tuple[str, str, str], ...] = (
    # (nombre, unidad, atributo)
    ("Rendimiento relativo (% del potencial)", "%", "ry"),
    ("Índice de estrés hídrico (0 = sin estrés, 1 = máximo)", "0–1", "stress"),
    ("Déficit de transpiración del ciclo", "mm", "deficit"),
    ("Lluvia efectiva del ciclo", "mm", "eff_rain"),
)


def climate_index(rows: Iterable[dict[str, Any]]) -> dict[date, DayClimate]:
    out: dict[date, DayClimate] = {}
    for r in rows:
        out[r["date"]] = DayClimate(r["date"], r.get("precip_mm"), r.get("t2m_max_c"), r.get("t2m_min_c"))
    return out


def _julaug_rain(climate: dict[date, DayClimate], year: int) -> float | None:
    vals = []
    for month, last in ((7, 31), (8, 31)):
        for day in range(1, last + 1):
            d = climate.get(date(year, month, day))
            if d is None or d.precip_mm is None:
                return None
            vals.append(d.precip_mm)
    return sum(vals)


def pick_scenario_years(
    seasons: dict[int, SeasonResult], julaug: dict[int, float]
) -> dict[str, list[int]]:
    """Años de cada escenario según la lluvia observada (igual para todas las estrategias)."""
    years = sorted(seasons)
    n = len(years)
    by_rain = sorted(years, key=lambda y: seasons[y].rain_mm)
    seco = by_rain[:GROUP]
    cand = [y for y in years if y in julaug]
    canicula = sorted(cand, key=lambda y: julaug[y])[:GROUP] if len(cand) >= GROUP else []
    lo, hi = n // 3, n - n // 3
    normal = by_rain[lo:hi] if hi - lo >= 1 else by_rain
    return {"normal": normal, "seco": seco, "canicula": canicula}


def _stats(values: Sequence[float]) -> tuple[float, float, float]:
    return statistics.fmean(values), min(values), max(values)


def _metric(res: SeasonResult, attr: str, ky: float) -> float:
    if attr == "ry":
        return 100.0 * relative_yield(res.stress, ky)
    if attr == "stress":
        return res.stress
    if attr == "deficit":
        return res.deficit_mm
    if attr == "eff_rain":
        return res.effective_rain_mm
    raise ValueError(attr)


def compute(
    climate: dict[date, DayClimate], lat_deg: float, last_date: date, first_date: date
) -> list[dict[str, Any]]:
    """Devuelve filas listas para `strategy_result` (sin ids: estrategia y cultivo por código)."""
    rows: list[dict[str, Any]] = []
    years = range(first_date.year, last_date.year + 1)
    for crop_code, crop in CROPS.items():
        # Años con ciclo completo para cada estrategia (la comparación usa los mismos años).
        per_strategy: dict[str, dict[int, SeasonResult]] = {}
        for code, mgmt in MANAGEMENT.items():
            seasons = {}
            for y in years:
                res = simulate_season(climate, y, crop, mgmt, lat_deg)
                if res is not None:
                    seasons[y] = res
            per_strategy[code] = seasons
        common = set.intersection(*(set(s) for s in per_strategy.values()))
        if len(common) < 5:
            continue  # sin una serie mínima no se calcula nada
        base = {y: per_strategy["E1"][y] for y in common}
        julaug = {y: v for y in common if (v := _julaug_rain(climate, y)) is not None}
        picked = pick_scenario_years(base, julaug)
        for scenario in SCENARIOS:
            sel = picked[scenario]
            if not sel:
                continue
            for code in MANAGEMENT:
                for name, unit, attr in INDICATORS:
                    values = [_metric(per_strategy[code][y], attr, crop.ky) for y in sel]
                    mid, lo, hi = _stats(values)
                    rows.append({
                        "strategy": code, "crop": crop_code, "scenario": scenario,
                        "indicator": name, "unit": unit,
                        "value_mid": round(mid, 3), "value_min": round(lo, 3), "value_max": round(hi, 3),
                    })
    return rows
