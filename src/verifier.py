"""
Verification dispatcher — picks a strategy via the classifier.

`classify()` reduces the dict AST to a `ConstraintType`; this module routes
each variant to the appropriate checker. The checkers themselves are stubs
for now; each branch documents the function that should fill it in.

`run_codeql` wraps the CodeQL CLI for the static-analysis branches (e.g.
hidden_error, future dataflow queries). It lives here rather than in
src/mapping/ because mapping is now a tiny source walk and no longer
needs CodeQL.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .constraints.classifier import classify
from .constraints.types import ConstraintType


QUERIES_DIR = Path(__file__).parent.parent / "queries"
_TMP_DIR    = Path("/tmp/codeql-results")


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


# ── CodeQL plumbing for static-analysis checkers ─────────────────────────

def run_query(db_path: str, query_file: str) -> list[dict]:
    """Run a CodeQL query against *db_path* and return the result rows."""
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    bqrs_path = _TMP_DIR / f"{query_file}.bqrs"
    json_path = _TMP_DIR / f"{query_file}.json"

    result = subprocess.run(
        ["codeql", "query", "run", str(QUERIES_DIR / query_file),
         "--database", db_path, "--output", str(bqrs_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"CodeQL query failed ({query_file}):\n"
                           f"{result.stderr.decode(errors='replace')}")

    result = subprocess.run(
        ["codeql", "bqrs", "decode", "--format=json",
         "--output", str(json_path), str(bqrs_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"CodeQL bqrs decode failed ({query_file}):\n"
                           f"{result.stderr.decode(errors='replace')}")

    with json_path.open() as f:
        data = json.load(f)
    select  = data.get("#select", {})
    columns = [col["name"] for col in select.get("columns", [])]
    tuples  = select.get("tuples", [])
    return [dict(zip(columns, row)) for row in tuples]


def run_codeql(query_file: str, db_path: str) -> dict:
    rows = run_query(db_path, query_file)
    return {"passed": len(rows) == 0, "violations": rows}
