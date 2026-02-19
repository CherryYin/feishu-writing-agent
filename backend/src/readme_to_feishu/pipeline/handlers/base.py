"""Handler interface - Attractor spec 4.1."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..graph import Graph, Node
    from ..context import Context
    from ..outcome import Outcome


class Handler(ABC):
    """Base interface for pipeline node handlers."""

    @abstractmethod
    def execute(
        self,
        node: Node,
        context: Context,
        graph: Graph,
        logs_root: Path,
    ) -> Outcome:
        """Execute the node and return outcome."""
        ...
