"""Sincronización incremental: trae solo lo que falta desde la última fecha cargada.

Cada fuente tiene una política:
  latency_days   retraso con el que la NASA publica el dato. La ventana termina en `hoy - latency_days`
                 para no pedir fechas que todavía no existen (valores conservadores, ver POLICIES).
  overlap_days   días que se vuelven a pedir antes de la última fecha cargada, porque la NASA puede
                 corregir los datos más recientes. El UPSERT hace que repetirlos no duplique nada.
  min_new_days   separación mínima entre datos nuevos (MODIS publica un compuesto cada 16 días);
                 mientras no pueda existir un dato nuevo, la fuente se marca "al día" sin consultar.
  chunk_days     tamaño máximo de cada petición, para que una descarga larga (la primera vez) avance
                 por tramos y, si falla, lo ya cargado se conserve.

Cada intento queda registrado en la tabla `ingest_run`, que alimenta el estado que muestra la página.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Sequence

from src.ingest.landsat_modis import HLS_COVERAGE_START, MODIS_COVERAGE_START
from src.ingest.smap import COVERAGE_START as SMAP_COVERAGE_START

POWER_COVERAGE_START = date(1981, 1, 1)


@dataclass(frozen=True)
class SourcePolicy:
    key: str
    label: str
    coverage_start: date
    latency_days: int
    overlap_days: int
    min_new_days: int
    chunk_days: int


# Latencias y solapes son estimaciones prudentes, no valores medidos: si la NASA publica más rápido,
# solo se pierde un par de días de frescura; si publicara más lento, el solape lo compensa al día siguiente.
POLICIES: dict[str, SourcePolicy] = {
    "power": SourcePolicy("power", "NASA POWER", POWER_COVERAGE_START, 5, 14, 1, 1826),
    "smap": SourcePolicy("smap", "SMAP", SMAP_COVERAGE_START, 5, 7, 1, 365),
    "modis": SourcePolicy("modis", "MODIS", MODIS_COVERAGE_START, 24, 32, 16, 730),
    "landsat": SourcePolicy("landsat", "Landsat/HLS", HLS_COVERAGE_START, 7, 15, 5, 365),
}
SYNC_ORDER = ("power", "smap", "modis", "landsat")


@dataclass
class SourceSpec:
    """Una fuente lista para sincronizar: su política y cómo descargar/cargar/consultar."""

    policy: SourcePolicy
    fetch: Callable[[date, date], list[dict[str, Any]]]
    load: Callable[[int, list[dict[str, Any]]], int]
    latest: Callable[[int], date | None]


@dataclass
class SyncResult:
    source: str
    status: str  # ok | up_to_date | error | planned
    start: date | None = None
    end: date | None = None
    rows: int = 0
    error: str | None = None


def plan_window(
    policy: SourcePolicy, last_date: date | None, today: date, default_start: date
) -> tuple[date, date] | None:
    """Ventana [inicio, fin] a pedir, o None si no puede haber datos nuevos."""
    end = today - timedelta(days=policy.latency_days)
    if last_date is None:
        start = max(default_start, policy.coverage_start)
    else:
        if (end - last_date).days < policy.min_new_days:
            return None
        start = max(last_date - timedelta(days=policy.overlap_days - 1), policy.coverage_start)
    if start > end:
        return None
    return start, end


def chunk_range(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    chunks, cursor = [], start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def run_sync(
    conn: Any,
    zone_id: int | None,
    specs: Sequence[SourceSpec],
    today: date,
    default_start: date,
    dry_run: bool = False,
    log: Callable[[str], None] = print,
) -> list[SyncResult]:
    """Sincroniza cada fuente por separado; una que falla no detiene a las demás."""
    from src.load import postgres

    results: list[SyncResult] = []
    for spec in specs:
        key, label = spec.policy.key, spec.policy.label
        tag = f"[{key.upper()}]"
        last = spec.latest(zone_id) if zone_id is not None else None
        window = plan_window(spec.policy, last, today, default_start)

        if window is None:
            log(f"{tag} {label}: al día (último dato: {last or 'ninguno'})")
            if not dry_run and zone_id is not None:
                run_id = postgres.start_run(conn, zone_id, key, None, None)
                postgres.finish_run(conn, run_id, "up_to_date", 0, last)
            results.append(SyncResult(key, "up_to_date"))
            continue

        start, end = window
        chunks = chunk_range(start, end, spec.policy.chunk_days)
        if dry_run:
            log(f"{tag} {label}: se pediría {start} -> {end} en {len(chunks)} tramo(s) (último dato: {last or 'ninguno'})")
            results.append(SyncResult(key, "planned", start, end))
            continue

        run_id = postgres.start_run(conn, zone_id, key, start, end)
        total = 0
        try:
            for i, (chunk_start, chunk_end) in enumerate(chunks, start=1):
                log(f"{tag} {label}: tramo {i}/{len(chunks)} {chunk_start} -> {chunk_end}")
                rows = spec.fetch(chunk_start, chunk_end)
                total += spec.load(zone_id, rows)
        except Exception as exc:  # una fuente que falla no debe detener a las demás
            conn.rollback()
            postgres.finish_run(conn, run_id, "error", total, spec.latest(zone_id), str(exc))
            log(f"{tag} ERROR: {exc}")
            results.append(SyncResult(key, "error", start, end, total, str(exc)))
            continue

        newest = spec.latest(zone_id)
        postgres.finish_run(conn, run_id, "ok", total, newest)
        log(f"{tag} {label}: {total} filas cargadas; datos hasta {newest or 'ninguno'}")
        results.append(SyncResult(key, "ok", start, end, total))
    return results
