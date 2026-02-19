"""Graph model for Attractor DOT pipeline - nodes and edges."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """Pipeline node with attributes (Attractor 2.6)."""

    id: str
    label: str = ""
    shape: str = "box"
    type: str = ""
    prompt: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.label or self.id


@dataclass
class Edge:
    """Directed edge with optional condition and label (Attractor 2.7)."""

    from_node: str
    to_node: str
    label: str = ""
    condition: str = ""
    weight: int = 0


@dataclass
class Graph:
    """Parsed pipeline graph (one digraph per file)."""

    name: str = ""
    goal: str = ""
    label: str = ""
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    graph_attrs: dict[str, Any] = field(default_factory=dict)

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def outgoing_edges(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.from_node == node_id]

    def find_start_node(self) -> str | None:
        """Resolve start: shape=Mdiamond or id in ('start','Start')."""
        for nid, node in self.nodes.items():
            if node.shape == "Mdiamond":
                return nid
        return self.nodes.get("start") and "start" or (
            self.nodes.get("Start") and "Start" or None
        )

    def is_terminal(self, node_id: str) -> bool:
        """Terminal: shape=Msquare or id in ('exit','end','Exit','End')."""
        node = self.get_node(node_id)
        if not node:
            return False
        if node.shape == "Msquare":
            return True
        return node_id.lower() in ("exit", "end")
