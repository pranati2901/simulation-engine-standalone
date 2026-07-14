"""Tiny, safe condition evaluator shared by the run loop and the cascade graph.

A condition is a single comparison against a known numeric context key, e.g.
`containment_rate == 1`, `attempts > 0`, `score < 100`. Deliberately NOT a general
expression evaluator — scenario/trigger definitions are authored by your team, but this
still avoids `eval()` entirely and stays deterministic.

Was inlined in engine/run.py; extracted so engine/graph.py can evaluate `Trigger`
conditions with the exact same semantics.
"""
from __future__ import annotations

import re

_CONDITION_RE = re.compile(r"^\s*([a-zA-Z_]\w*)\s*(>=|<=|==|!=|>|<)\s*([\d.]+)\s*$")
_OPS = {
    ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b, ">": lambda a, b: a > b, "<": lambda a, b: a < b,
}

# Conditions that read as "the operator did NOT contain/prevent the fault". A cascade
# edge firing on one of these is a *preventable* consequence — it would not have
# happened had the root fault been correctly resolved. The graph uses this to answer
# "which downstream effects were avoidable?".
_PREVENTABILITY_KEYS = ("containment", "contained", "certified", "score")


def eval_condition(condition: str, context: dict[str, float]) -> bool:
    """Evaluate a single-comparison condition string against a numeric context.

    Empty / "always" / "true" always fire. Unknown keys or malformed conditions
    evaluate to False (fail closed).
    """
    c = (condition or "").strip().lower()
    if c in ("", "always", "true"):
        return True
    m = _CONDITION_RE.match(condition)
    if not m:
        return False
    key, op, value = m.group(1), m.group(2), float(m.group(3))
    if key not in context:
        return False
    return _OPS[op](context[key], value)


def is_preventable_condition(condition: str) -> bool:
    """True if this condition fires *because the operator failed to contain the fault*
    (so the consequence it triggers was avoidable). See _PREVENTABILITY_KEYS."""
    return any(k in (condition or "").lower() for k in _PREVENTABILITY_KEYS)
