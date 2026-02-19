"""Pipeline execution engine - Attractor spec Section 3."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .graph import Graph, Node, Edge
from .context import Context
from .outcome import Outcome, StageStatus
from .conditions import evaluate_condition
from .handlers import StartHandler, ExitHandler, CodergenHandler, ToolHandler
from .handlers.tool import ToolExecutor

# Event callback: (event_kind, data) -> None
EventCallback = Callable[[str, dict[str, Any]], None]

SHAPE_TO_TYPE: dict[str, str] = {
    "Mdiamond": "start",
    "Msquare": "exit",
    "box": "codergen",
    "parallelogram": "tool",
    "diamond": "conditional",
    "hexagon": "wait.human",
    "component": "parallel",
    "tripleoctagon": "parallel.fan_in",
    "house": "stack.manager_loop",
}


def _normalize_label(label: str) -> str:
    s = (label or "").strip().lower()
    # Strip accelerator prefixes like "[Y] ", "Y) ", "Y - "
    if s.startswith("[") and "]" in s[:4]:
        s = s.split("]", 1)[1].strip()
    if len(s) >= 2 and s[1:2] == ")":
        s = s[2:].strip()
    if len(s) >= 3 and s[1:3] == " -":
        s = s[3:].strip()
    return s.strip()


def select_edge(
    node: Node,
    outcome: Outcome,
    context: Context,
    graph: Graph,
) -> Edge | None:
    """Attractor 3.3: condition match -> preferred label -> suggested_next_ids -> weight -> lexical."""
    edges = graph.outgoing_edges(node.id)
    if not edges:
        return None

    # Step 1: condition-matching
    condition_matched = [
        e for e in edges if e.condition and evaluate_condition(e.condition, outcome, context)
    ]
    if condition_matched:
        # weight DESC, to_node ASC
        return sorted(condition_matched, key=lambda e: (-e.weight, e.to_node))[0]

    # Step 2: preferred label
    if outcome.preferred_label:
        pl = _normalize_label(outcome.preferred_label)
        for e in edges:
            if _normalize_label(e.label) == pl:
                return e

    # Step 3: suggested_next_ids
    if outcome.suggested_next_ids:
        for sid in outcome.suggested_next_ids:
            for e in edges:
                if e.to_node == sid:
                    return e

    # Step 4 & 5: unconditional by weight then lexical
    unconditional = [e for e in edges if not e.condition]
    if unconditional:
        return sorted(unconditional, key=lambda e: (-e.weight, e.to_node))[0]

    # Fallback (spec): any edge by weight then lexical
    return sorted(edges, key=lambda e: (-e.weight, e.to_node))[0]


class PipelineEngine:
    """Runs a parsed graph from start to exit, with handler registry and event emission."""

    def __init__(
        self,
        codergen_backend: CodergenHandler | None = None,
        tool_executors: dict[str, ToolExecutor] | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self._handlers: dict[str, Any] = {
            "start": StartHandler(),
            "exit": ExitHandler(),
            "codergen": codergen_backend or CodergenHandler(),
            "tool": ToolHandler(executors=tool_executors or {}),
            "conditional": _ConditionalHandler(),
        }
        self._on_event = on_event or (lambda k, d: None)

    def _resolve_handler(self, node: Node) -> Any:
        if node.type:
            h = self._handlers.get(node.type)
            if h is not None:
                return h
        handler_type = SHAPE_TO_TYPE.get(node.shape, "codergen")
        return self._handlers.get(handler_type, self._handlers["codergen"])

    def run(
        self,
        graph: Graph,
        context: Context | None = None,
        logs_root: Path | None = None,
    ) -> Outcome:
        ctx = context or Context()
        logs_root = logs_root or Path(".")
        ctx.set("graph.goal", graph.goal)
        ctx.set("graph.label", graph.label)

        start_id = graph.find_start_node()
        if not start_id:
            raise ValueError("No start node (shape=Mdiamond or id=start) found")
        current_id = start_id
        node_outcomes: dict[str, Outcome] = {}
        last_outcome: Outcome | None = None

        while True:
            node = graph.get_node(current_id)
            if not node:
                raise RuntimeError(f"Node not found: {current_id}")

            if graph.is_terminal(current_id):
                # Goal gate enforcement (Attractor 3.4, simplified):
                # If any goal_gate node is not SUCCESS/PARTIAL_SUCCESS, fail the pipeline.
                for nid, oc in node_outcomes.items():
                    n = graph.get_node(nid)
                    if not n:
                        continue
                    if bool(n.attrs.get("goal_gate")):
                        if oc.status not in (StageStatus.SUCCESS, StageStatus.PARTIAL_SUCCESS):
                            fail = Outcome(
                                status=StageStatus.FAIL,
                                failure_reason=f"Goal gate unsatisfied at node '{nid}': {oc.failure_reason or oc.status.value}",
                            )
                            self._on_event("PipelineFailed", {"node_id": nid, "reason": fail.failure_reason})
                            return fail
                break

            handler = self._resolve_handler(node)
            self._on_event("StageStarted", {"node_id": node.id, "label": node.display_name})
            outcome = handler.execute(node, ctx, graph, logs_root)
            node_outcomes[current_id] = outcome
            last_outcome = outcome
            ctx.apply_updates(outcome.context_updates)
            ctx.set("outcome", outcome.status.value)
            if outcome.preferred_label:
                ctx.set("preferred_label", outcome.preferred_label)

            (logs_root / node.id).mkdir(parents=True, exist_ok=True)
            status_path = logs_root / node.id / "status.json"
            if status_path.exists() is False and outcome.status != StageStatus.FAIL:
                import json
                status_path.write_text(json.dumps(outcome.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

            self._on_event("StageCompleted", {"node_id": node.id, "outcome": outcome.status.value, "notes": outcome.notes})

            # Failure routing (Attractor 3.7): if a stage FAILs and no fail edge matches, terminate.
            if outcome.status == StageStatus.FAIL:
                fail_edges = [
                    e
                    for e in graph.outgoing_edges(node.id)
                    if e.condition and evaluate_condition(e.condition, outcome, ctx)
                ]
                if fail_edges:
                    next_edge = sorted(fail_edges, key=lambda e: (-e.weight, e.to_node))[0]
                else:
                    raise RuntimeError(f"Stage '{node.id}' failed: {outcome.failure_reason}")
            else:
                next_edge = select_edge(node, outcome, ctx, graph)
                if next_edge is None:
                    break
            current_id = next_edge.to_node

        self._on_event("PipelineCompleted", {"current_node": current_id})
        return last_outcome or Outcome(status=StageStatus.SUCCESS, notes="Pipeline completed")


class _ConditionalHandler:
    """No-op; routing is done by edge conditions in select_edge."""

    def execute(self, node: Node, context: Context, graph: Graph, logs_root: Path) -> Outcome:
        from ..outcome import Outcome, StageStatus
        return Outcome(status=StageStatus.SUCCESS, notes=f"Conditional: {node.id}")
