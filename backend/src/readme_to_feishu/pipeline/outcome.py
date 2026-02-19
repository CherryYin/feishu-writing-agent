"""Pipeline outcome - Attractor spec Section 5.2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class StageStatus(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"
    PARTIAL_SUCCESS = "partial_success"
    RETRY = "retry"
    SKIPPED = "skipped"


@dataclass
class Outcome:
    """Result of executing a node handler."""

    status: StageStatus
    preferred_label: str = ""
    suggested_next_ids: list[str] | None = None
    context_updates: dict[str, Any] | None = None
    notes: str = ""
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.status.value,
            "preferred_next_label": self.preferred_label,
            "suggested_next_ids": self.suggested_next_ids or [],
            "context_updates": self.context_updates or {},
            "notes": self.notes,
            "failure_reason": self.failure_reason,
        }
