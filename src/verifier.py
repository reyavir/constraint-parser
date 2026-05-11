"""
Verification dispatcher — picks a strategy via the classifier.

`classify()` reduces the dict AST to a `ConstraintType`; this module routes
each variant to the appropriate checker. The checkers themselves are stubs
for now; each branch documents the function that should fill it in.
"""

from __future__ import annotations

from typing import Any

from .constraints.classifier import classify
from .constraints.types import ConstraintType
from .mapping.codeql_runner import run_query


def verify(
    ast: dict,
    traces: Any = None,
    network_log: Any = None,
    db_path: str = "./codeql-db",
) -> dict[str, Any]:
    ctype = classify(ast)
    match ctype:
        case ConstraintType.PROBABILISTIC:  return _todo(ctype, "check_probabilistic(ast, traces)")
        case ConstraintType.VALUE:          return _todo(ctype, "check_value(ast, traces)")
        case ConstraintType.VALUE_WITH_DATAFLOW:
            return _todo(ctype, "check_value(ast, traces) + run_codeql(dataflow_query, db_path)")
        case ConstraintType.COUNTERFACTUAL: return _todo(ctype, "check_counterfactual(ast, traces)")
        case ConstraintType.API_CALL:       return _todo(ctype, "check_api_call(ast, traces, network_log)")
        case ConstraintType.COMPOUND:       return _todo(ctype, "check_compound(ast, traces)")
        case ConstraintType.EXCLUSIVE:      return _todo(ctype, "check_exclusive(ast, traces)")
        case ConstraintType.LENGTH_MATCH:   return _todo(ctype, "check_length(ast, traces)")
        case ConstraintType.ORDER:          return _todo(ctype, "check_order(ast, traces)")
        case ConstraintType.STATIC:         return _todo(ctype, "run_codeql(query, db_path)")
        case _:
            raise NotImplementedError(f"No verifier mapped to {ctype}.")


def _todo(ctype: ConstraintType, hint: str) -> dict:
    raise NotImplementedError(
        f"Verifier for {ctype.name} is not implemented yet — wire up {hint}."
    )


def run_codeql(query_file: str, db_path: str) -> dict:
    rows = run_query(db_path, query_file)
    return {"passed": len(rows) == 0, "violations": rows}
