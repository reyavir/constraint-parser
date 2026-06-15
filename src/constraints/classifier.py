"""
Map a dict AST to a ConstraintType to choose the verification strategy.

Each branch just reads a couple of fields the Visitor 1 already extracted —
no extra tree walking required.

Priority order (first match wins):

  1. event is a CallEvent                 → API_CALL
  2. condition is a negated user action   → COUNTERFACTUAL
  3. WriteEvent that carries a value_expr → VALUE or VALUE_WITH_DATAFLOW
       (see _classify_value_expr — depends on whether the value is a constant /
        external source or whether it derives from another UI element)
  4. event is a Guard                     → GUARD
  5. event is a CompoundEvent
        op == "XOR"                       → EXCLUSIVE
        op == "AND" or "OR"               → COMPOUND
  6. otherwise                            → PROBABILISTIC

The classifier assumes the AST has already passed semantic analysis. Invalid
shapes (e.g. Action on the event side) still classify to *something* — the
caller is expected to surface semantic errors separately.
"""

from __future__ import annotations

from .types import ConstraintType


def classify(ast: dict) -> ConstraintType:
    event     = ast.get("event") or {}
    condition = ast.get("condition") or {}

    if event.get("type") == "CallEvent":
        return ConstraintType.API_CALL

    if event.get("type") == "PersistEvent":
        return ConstraintType.PERSIST

    if condition.get("negated"):
        return ConstraintType.COUNTERFACTUAL

    if event.get("type") == "WriteEvent" and event.get("value_expr") is not None:
        return _classify_value_expr(event["value_expr"])

    # Explicit-set form `w(target, sources={...})` — value derives from
    # exactly the listed element reads. Routes to source_set primitive
    # like the arithmetic VALUE_WITH_DATAFLOW form.
    if event.get("type") == "WriteEvent" and event.get("sources") is not None:
        return ConstraintType.VALUE_WITH_DATAFLOW

    if event.get("type") == "Guard":
        return ConstraintType.GUARD

    if event.get("type") == "CompoundEvent":
        return (ConstraintType.EXCLUSIVE
                if event.get("op") == "XOR"
                else ConstraintType.COMPOUND)

    return ConstraintType.PROBABILISTIC


# ---------------------------------------------------------------------------
# value_expr → VALUE vs VALUE_WITH_DATAFLOW
# ---------------------------------------------------------------------------
#
# The key question: does the written value derive from another UI element?
#   - If YES, runtime alone is insufficient — the values could match by
#     coincidence (e.g. the target is hardcoded). We need CodeQL to confirm
#     a data-flow path exists from the source element to the target.
#   - If NO (constant or external source like api_result), runtime is enough.

_DATAFLOW_VEXPR_TYPES = {"ReadExpr", "FuncExpr", "IncrementExpr", "BinaryExpr"}
_CONSTANT_VEXPR_TYPES = {"LiteralExpr", "LenExpr", "StatusExpr"}


def _classify_value_expr(ve: dict) -> ConstraintType:
    vtype = ve.get("type")
    if vtype in _DATAFLOW_VEXPR_TYPES:
        return ConstraintType.VALUE_WITH_DATAFLOW
    if vtype in _CONSTANT_VEXPR_TYPES:
        return ConstraintType.VALUE
    # Unknown shape — be conservative and demand both checks.
    return ConstraintType.VALUE_WITH_DATAFLOW
