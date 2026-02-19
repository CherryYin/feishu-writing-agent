"""Start handler - Attractor spec 4.3."""

from pathlib import Path

from ..graph import Graph, Node
from ..context import Context
from ..outcome import Outcome, StageStatus

from .base import Handler


class StartHandler(Handler):
    """No-op entry point; returns SUCCESS immediately."""

    def execute(
        self,
        node: Node,
        context: Context,
        graph: Graph,
        logs_root: Path,
    ) -> Outcome:
        return Outcome(status=StageStatus.SUCCESS, notes=f"Start: {node.id}")
