"""Tool handler - Attractor spec 4.10: execute external tool via node attributes."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from ..graph import Graph, Node
from ..context import Context
from ..outcome import Outcome, StageStatus

from .base import Handler


# Optional: tool_name -> (node, context, graph, logs_root) -> Outcome
ToolExecutor = Callable[[str, Node, Context, Graph, Path], Outcome | None]


class ToolHandler(Handler):
    """Execute a tool configured via node attrs (e.g. tool_command or custom tool name)."""

    def __init__(self, executors: dict[str, ToolExecutor] | None = None) -> None:
        self.executors = executors or {}

    def execute(
        self,
        node: Node,
        context: Context,
        graph: Graph,
        logs_root: Path,
    ) -> Outcome:
        tool_name = node.attrs.get("tool") or node.attrs.get("tool_command")
        if isinstance(tool_name, str) and tool_name in self.executors:
            try:
                return self.executors[tool_name](tool_name, node, context, graph, logs_root)
            except Exception as e:
                return Outcome(status=StageStatus.FAIL, failure_reason=str(e))

        command = node.attrs.get("tool_command", "")
        if not command:
            return Outcome(
                status=StageStatus.FAIL,
                failure_reason="No tool_command or registered tool specified",
            )
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=context.get("work_dir") or ".",
            )
            out = (result.stdout or "") + (result.stderr or "")
            return Outcome(
                status=StageStatus.SUCCESS if result.returncode == 0 else StageStatus.FAIL,
                context_updates={"tool.output": out},
                notes=f"Tool completed: {command}",
                failure_reason="" if result.returncode == 0 else out or f"exit code {result.returncode}",
            )
        except subprocess.TimeoutExpired:
            return Outcome(status=StageStatus.FAIL, failure_reason="Tool timed out")
        except Exception as e:
            return Outcome(status=StageStatus.FAIL, failure_reason=str(e))
