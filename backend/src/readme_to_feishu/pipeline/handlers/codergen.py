"""Codergen handler - Attractor spec 4.5: LLM task with backend."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Any

from ..graph import Graph, Node
from ..context import Context
from ..outcome import Outcome, StageStatus

from .base import Handler


# CodergenBackend: run(node, prompt, context) -> str | Outcome
CodergenBackend = Callable[[Node, str, Context], str | Outcome]


class CodergenHandler(Handler):
    """LLM stage: expand $goal, call backend, write prompt/response to logs."""

    def __init__(self, backend: CodergenBackend | None = None) -> None:
        self.backend = backend

    def execute(
        self,
        node: Node,
        context: Context,
        graph: Graph,
        logs_root: Path,
    ) -> Outcome:
        stage_dir = logs_root / node.id
        stage_dir.mkdir(parents=True, exist_ok=True)

        prompt = node.prompt or node.label
        goal = context.get_string("graph.goal") or graph.goal
        prompt = prompt.replace("$goal", goal)

        (stage_dir / "prompt.md").write_text(prompt, encoding="utf-8")

        if self.backend:
            try:
                result = self.backend(node, prompt, context)
                if isinstance(result, Outcome):
                    (stage_dir / "status.json").write_text(
                        __import__("json").dumps(result.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    return result
                response_text = str(result)
            except Exception as e:
                outcome = Outcome(
                    status=StageStatus.FAIL,
                    failure_reason=str(e),
                )
                (stage_dir / "status.json").write_text(
                    __import__("json").dumps(outcome.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return outcome
        else:
            response_text = f"[Simulated] Response for stage: {node.id}"

        (stage_dir / "response.md").write_text(response_text, encoding="utf-8")
        outcome = Outcome(
            status=StageStatus.SUCCESS,
            notes=f"Stage completed: {node.id}",
            context_updates={
                "last_stage": node.id,
                "last_response": response_text[:200] if response_text else "",
            },
        )
        (stage_dir / "status.json").write_text(
            __import__("json").dumps(outcome.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return outcome
