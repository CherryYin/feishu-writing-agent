"""Pipeline context - Attractor spec Section 5.1: key-value store shared across stages."""

from __future__ import annotations

import copy
from typing import Any


class Context:
    """Thread-safe key-value store for pipeline run state."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._logs: list[str] = []

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def get_string(self, key: str, default: str = "") -> str:
        v = self.get(key)
        if v is None:
            return default
        return str(v)

    def append_log(self, entry: str) -> None:
        self._logs.append(entry)

    def snapshot(self) -> dict[str, Any]:
        return dict(self._values)

    def clone(self) -> Context:
        c = Context()
        c._values = copy.copy(self._values)
        c._logs = list(self._logs)
        return c

    def apply_updates(self, updates: dict[str, Any] | None) -> None:
        if not updates:
            return
        self._values.update(updates)
