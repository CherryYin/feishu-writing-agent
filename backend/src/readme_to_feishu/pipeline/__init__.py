"""Attractor-compliant pipeline: DOT parsing, engine, handlers."""

from .graph import Graph, Node, Edge
from .context import Context
from .outcome import Outcome, StageStatus
from .dot_parser import parse_dot
from .engine import PipelineEngine, select_edge, SHAPE_TO_TYPE

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "Context",
    "Outcome",
    "StageStatus",
    "parse_dot",
    "PipelineEngine",
    "select_edge",
    "SHAPE_TO_TYPE",
]
