"""Utilidades para convertir filas de AppEEARS en series diarias."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable


def to_float(text: str | None) -> float | None:
    """Convierte texto del CSV a float. Vacío o no numérico (NaN) -> None."""
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return None if value != value else value  # descarta NaN


def parse_date(text: str) -> date:
    """AppEEARS entrega 'AAAA-MM-DD' (a veces con hora): se usa solo la fecha."""
    return date.fromisoformat(text.strip()[:10])


class DailyMean:
    """Acumula valores por fecha y devuelve el promedio, ignorando los datos faltantes (None)."""

    def __init__(self) -> None:
        self._values: dict[date, list[float]] = defaultdict(list)

    def add(self, day: date, value: float | None) -> None:
        if value is not None:
            self._values[day].append(value)

    def means(self) -> dict[date, float]:
        return {day: sum(vals) / len(vals) for day, vals in self._values.items()}


def merge_by_date(series: dict[str, dict[date, float]]) -> list[dict]:
    """Une varias series por fecha. {'a': {d: 1}, 'b': {d: 2}} -> [{'date': d, 'a': 1, 'b': 2}]."""
    days: set[date] = set()
    for values in series.values():
        days.update(values)
    rows = []
    for day in sorted(days):
        row: dict = {"date": day}
        for name, values in series.items():
            row[name] = values.get(day)
        rows.append(row)
    return rows


def rows_with_data(rows: Iterable[dict], keys: Iterable[str]) -> list[dict]:
    """Descarta filas donde todas las variables indicadas son None."""
    keys = tuple(keys)
    return [r for r in rows if any(r.get(k) is not None for k in keys)]
