"""Condition expression evaluation - Attractor spec Section 10."""

from __future__ import annotations

from .outcome import Outcome
from .context import Context


def resolve_key(key: str, outcome: Outcome, context: Context) -> str:
    key = key.strip()
    if key == "outcome":
        return outcome.status.value
    if key == "preferred_label":
        return outcome.preferred_label or ""
    if key.startswith("context."):
        k = key[9:].strip()
        v = context.get(k)
        if v is not None:
            return str(v)
        v = context.get(key)
        if v is not None:
            return str(v)
        return ""
    v = context.get(key)
    if v is not None:
        return str(v)
    return ""


def evaluate_clause(clause: str, outcome: Outcome, context: Context) -> bool:
    clause = clause.strip()
    if "!=" in clause:
        parts = clause.split("!=", 1)
        key = parts[0].strip()
        val = parts[1].strip().strip('"')
        return resolve_key(key, outcome, context) != val
    if "=" in clause:
        parts = clause.split("=", 1)
        key = parts[0].strip()
        val = parts[1].strip().strip('"')
        return resolve_key(key, outcome, context) == val
    return bool(resolve_key(clause, outcome, context))


def evaluate_condition(condition: str, outcome: Outcome, context: Context) -> bool:
    if not condition or not condition.strip():
        return True
    clauses = [c.strip() for c in condition.split("&&") if c.strip()]
    for clause in clauses:
        if not evaluate_clause(clause, outcome, context):
            return False
    return True
