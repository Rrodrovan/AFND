"""Balance hídrico diario simple para un cultivo, con datos de NASA POWER.

Método (todo con fórmulas publicadas, sin datos de campo):
  * ET0 de referencia: Hargreaves-Samani (1985), con la radiación extraterrestre de FAO-56 (ec. 21).
  * Demanda del cultivo: Kc = Kcb + Ke (FAO-56, tablas 12 y 17). Kcb es la transpiración (la que da rendimiento) y
    Ke la evaporación del suelo descubierto (la que reducen las coberturas).
  * Un "cubo" de agua en el suelo (capacidad TAW): la lluvia efectiva lo llena, el cultivo lo vacía.
    Cuando el agua fácilmente disponible se agota, la evapotranspiración real (ETa) baja (FAO-56, cap. 8).
  * Rendimiento relativo = 1 − Ky × (1 − ETa/ETc) (FAO-33, Doorenbos y Kassam, 1979).

Es un modelo de estimación para comparar estrategias bajo la misma lluvia y temperatura observadas.
Los parámetros de cada estrategia (escorrentía, evaporación, capacidad del suelo) son supuestos
explícitos y ajustables: ver `strategies.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

SOLAR_CONSTANT = 0.0820  # MJ m-2 min-1
PRESEASON_DAYS = 30      # el cubo se simula desde 30 días antes de la siembra
PRESEASON_START_FRACTION = 0.30


@dataclass(frozen=True)
class Crop:
    code: str
    sow_month: int
    sow_day: int
    stages: tuple[int, int, int, int]   # días: inicial, desarrollo, media, final
    kc_ini: float
    kc_mid: float
    kc_end: float
    kcb_ini: float
    kcb_mid: float
    kcb_end: float
    ky: float                            # sensibilidad del rendimiento al déficit (FAO-33)
    depletion_p: float                   # fracción de TAW agotable sin estrés (FAO-56, tabla 22)
    taw_mm: float                        # agua útil del suelo en la zona de raíces

    @property
    def cycle_days(self) -> int:
        return sum(self.stages)


@dataclass(frozen=True)
class Management:
    """Efecto de una estrategia de manejo sobre el balance (supuestos explícitos)."""
    runoff: float = 0.15        # fracción de la lluvia que se pierde por escorrentía
    evap_factor: float = 1.0    # multiplica la evaporación del suelo (Ke); < 1 con cobertura o mulch
    taw_mult: float = 1.0       # multiplica la capacidad de agua útil del suelo


@dataclass(frozen=True)
class DayClimate:
    day: date
    precip_mm: float | None
    tmax_c: float | None
    tmin_c: float | None


@dataclass(frozen=True)
class SeasonResult:
    year: int
    rain_mm: float          # lluvia total observada del ciclo (sin descontar escorrentía)
    effective_rain_mm: float
    tc_mm: float            # transpiración potencial del ciclo
    ta_mm: float            # transpiración real del ciclo

    @property
    def deficit_mm(self) -> float:
        return max(0.0, self.tc_mm - self.ta_mm)

    @property
    def stress(self) -> float:
        return 0.0 if self.tc_mm <= 0 else min(1.0, max(0.0, 1.0 - self.ta_mm / self.tc_mm))


def relative_yield(stress: float, ky: float) -> float:
    """Rendimiento relativo (0–1) a partir del estrés hídrico del ciclo."""
    return min(1.0, max(0.0, 1.0 - ky * stress))


def extraterrestrial_radiation_mm(lat_deg: float, doy: int) -> float:
    """Radiación extraterrestre diaria en mm/día equivalentes (FAO-56, ec. 21 × 0,408)."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * doy)
    delta = 0.409 * math.sin(2 * math.pi / 365 * doy - 1.39)
    x = -math.tan(phi) * math.tan(delta)
    ws = math.acos(max(-1.0, min(1.0, x)))
    ra = (24 * 60 / math.pi) * SOLAR_CONSTANT * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )
    return 0.408 * ra


def et0_hargreaves(tmax_c: float, tmin_c: float, lat_deg: float, doy: int) -> float:
    tmean = (tmax_c + tmin_c) / 2
    ra = extraterrestrial_radiation_mm(lat_deg, doy)
    return max(0.0, 0.0023 * ra * (tmean + 17.8) * math.sqrt(max(tmax_c - tmin_c, 0.0)))


def _curve(crop: Crop, day_index: int, v_ini: float, v_mid: float, v_end: float) -> float:
    ini, dev, mid, late = crop.stages
    if day_index < ini:
        return v_ini
    if day_index < ini + dev:
        return v_ini + (v_mid - v_ini) * (day_index - ini) / dev
    if day_index < ini + dev + mid:
        return v_mid
    if day_index < ini + dev + mid + late:
        return v_mid + (v_end - v_mid) * (day_index - ini - dev - mid) / late
    return v_end


def kc_at(crop: Crop, day_index: int) -> float:
    """Kc total del día `day_index` del ciclo (0 = siembra), con transiciones lineales (FAO-56)."""
    return _curve(crop, day_index, crop.kc_ini, crop.kc_mid, crop.kc_end)


def kcb_at(crop: Crop, day_index: int) -> float:
    """Kcb (solo transpiración) del día `day_index` del ciclo."""
    return _curve(crop, day_index, crop.kcb_ini, crop.kcb_mid, crop.kcb_end)


def _fill_missing(days: Sequence[DayClimate]) -> list[DayClimate] | None:
    """Rellena huecos aislados; devuelve None si falta más del 5 % de los datos."""
    missing = sum(1 for d in days if d.precip_mm is None or d.tmax_c is None or d.tmin_c is None)
    if len(days) == 0 or missing / len(days) > 0.05:
        return None
    filled: list[DayClimate] = []
    last_tmax = last_tmin = None
    for d in days:
        tmax = d.tmax_c if d.tmax_c is not None else last_tmax
        tmin = d.tmin_c if d.tmin_c is not None else last_tmin
        if tmax is None or tmin is None:
            nxt = next((x for x in days if x.tmax_c is not None and x.tmin_c is not None), None)
            if nxt is None:
                return None
            tmax, tmin = nxt.tmax_c, nxt.tmin_c
        last_tmax, last_tmin = tmax, tmin
        filled.append(DayClimate(d.day, d.precip_mm if d.precip_mm is not None else 0.0, tmax, tmin))
    return filled


def simulate_season(
    climate: dict[date, DayClimate], year: int, crop: Crop, mgmt: Management, lat_deg: float
) -> SeasonResult | None:
    """Simula un ciclo. Devuelve None si el ciclo no está completo o faltan demasiados datos."""
    sow = date(year, crop.sow_month, crop.sow_day)
    start = sow - timedelta(days=PRESEASON_DAYS)
    end = sow + timedelta(days=crop.cycle_days - 1)
    span = [climate.get(start + timedelta(days=i)) for i in range((end - start).days + 1)]
    if any(d is None for d in span):
        return None
    days = _fill_missing(span)  # type: ignore[arg-type]
    if days is None:
        return None

    taw = crop.taw_mm * mgmt.taw_mult
    store = taw * PRESEASON_START_FRACTION
    raw = crop.depletion_p * taw          # agua fácilmente disponible
    rain = eff_rain = tc_sum = ta_sum = 0.0

    for d in days:
        idx = (d.day - sow).days
        in_cycle = idx >= 0
        peff = d.precip_mm * (1 - mgmt.runoff)
        store = min(taw, store + peff)     # lo que excede la capacidad se pierde por drenaje

        et0 = et0_hargreaves(d.tmax_c, d.tmin_c, lat_deg, d.day.timetuple().tm_yday)
        kc = kc_at(crop, idx) if in_cycle else crop.kc_ini
        kcb = kcb_at(crop, idx) if in_cycle else crop.kcb_ini
        ke = max(0.0, kc - kcb)

        # 1) evaporación del suelo (la reducen las coberturas); 2) transpiración del cultivo.
        store -= min(store, ke * et0 * mgmt.evap_factor)
        tc = kcb * et0
        depletion = taw - store
        ks = 1.0 if depletion <= raw else max(0.0, (taw - depletion) / (taw - raw))
        ta = min(store, ks * tc)
        store -= ta

        if in_cycle:
            rain += d.precip_mm
            eff_rain += peff
            tc_sum += tc
            ta_sum += ta

    return SeasonResult(year, rain, eff_rain, tc_sum, ta_sum)
