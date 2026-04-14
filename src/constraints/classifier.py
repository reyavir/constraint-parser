"""
Constraint classifier.

Takes a parsed AST node (ProbabilisticConstraint or StaticConstraint) and
returns the appropriate ConstraintType so callers can dispatch to the right
verification strategy.

Usage
-----
    from src.parser import parse
    from src.constraints import classify, ConstraintType

    ast = parse("P(w(cartDisplay) | A(addBtn)) = 1")
    ctype = classify(ast)
    assert ctype == ConstraintType.PROBABILISTIC
"""

from __future__ import annotations

from ..parser.ast_nodes import (
    ProbabilisticConstraint,
    StaticConstraint,
    WriteEvent,
    CompoundWriteEvent,
    SeqOrderEvent,
    LenMatchEvent,
    ApiCallEvent,
    ActionCondition,
)
from .types import ConstraintType


def classify(constraint: ProbabilisticConstraint | StaticConstraint) -> ConstraintType:
    """
    Map a parsed constraint to its ConstraintType.

    Raises
    ------
    TypeError
        If *constraint* is not a recognised top-level AST node.
    """
    if isinstance(constraint, StaticConstraint):
        return ConstraintType.STATIC

    if isinstance(constraint, ProbabilisticConstraint):
        return _classify_probabilistic(constraint)

    raise TypeError(f"Cannot classify unknown constraint node: {type(constraint)!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify_probabilistic(c: ProbabilisticConstraint) -> ConstraintType:
    event = c.event
    condition = c.condition

    # ── Event-driven types ────────────────────────────────────────────────

    if isinstance(event, ApiCallEvent):
        return ConstraintType.API_CALL

    if isinstance(event, SeqOrderEvent):
        return ConstraintType.ORDER

    if isinstance(event, LenMatchEvent):
        return ConstraintType.LENGTH_MATCH

    if isinstance(event, CompoundWriteEvent):
        return ConstraintType.COMPOUND if event.op == "AND" else ConstraintType.EXCLUSIVE

    # ── Write event variants ──────────────────────────────────────────────

    if isinstance(event, WriteEvent):
        # Negated condition → counterfactual
        if isinstance(condition, ActionCondition) and condition.negated:
            return ConstraintType.COUNTERFACTUAL

        # Write with value expression → value constraint
        if event.value_expr is not None:
            return ConstraintType.VALUE

        # Plain write with straight action → probabilistic
        return ConstraintType.PROBABILISTIC

    # Fallback: treat unrecognised write-like events as probabilistic
    return ConstraintType.PROBABILISTIC
