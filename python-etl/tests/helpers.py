"""Respuestas simuladas para probar el cliente de AppEEARS sin acceso a la red."""

from __future__ import annotations

import csv
import io
from typing import Any, Callable


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: Any = None, content: bytes = b""):
        self.status_code = status_code
        self._json = json_data
        self.content = content
        self.text = content.decode("utf-8", "replace") if content else str(json_data)

    def json(self) -> Any:
        return self._json


class FakeSession:
    """Sesión que delega cada petición en `handler(method, url, kwargs)` y las registra."""

    def __init__(self, handler: Callable[[str, str, dict], FakeResponse]):
        self.handler = handler
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return self.handler(method, url, kwargs)


def csv_rows(text: str) -> list[dict[str, str]]:
    """Convierte texto CSV en la lista de filas que entrega el cliente."""
    return list(csv.DictReader(io.StringIO(text.strip())))
