"""Exit handler - Attractor spec 4.4."""

from pathlib import Path

from ..graph import Graph, Node
from ..context import Context
from ..outcome import Outcome, StageStatus

from .base import Handler


class ExitHandler(Handler):
    """No-op exit point; goal gate check is done by the engine."""

    def execute(
        self,
        node: Node,
        context: Context,
        graph: Graph,
        logs_root: Path,
    ) -> Outcome:
        return Outcome(status=StageStatus.SUCCESS, notes=f"Exit: {node.id}")
