"""Indicadores básicos de sequía a partir de precipitación diaria."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Sequence


def longest_dry_spell(precip_mm: Sequence[float | None], threshold_mm: float = 1.0) -> int:
    """Racha más larga de días secos consecutivos.

    Un día es seco si la precipitación es menor que `threshold_mm`.
    Un dato faltante (None) interrumpe la racha, para no inventar días secos.
    """
    longest = current = 0
    for value in precip_mm:
        if value is not None and value < threshold_mm:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def monthly_totals(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    """Precipitación acumulada por mes ('YYYY-MM') a partir de filas de `climate_daily`."""
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        precip = row.get("precip_mm")
        if precip is not None:
            totals[row["date"].strftime("%Y-%m")] += precip
    return dict(totals)
