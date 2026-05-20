"""
Stage 1 — static (CodeQL-based) checks that run before any runtime tracing.

Only handles UI-to-UI constraints. Anything that involves the network, a
counterfactual, length comparison, or sequencing is returned as SKIP so the
caller can fall through to whatever future stages cover those cases.

Public entry point:
    stage1_check(ast, db_path) -> {
        "result":  "PASSED" | "FLAGGED" | "SKIP",
        "reason":  str | None,
        "checks":  [
            {
                "name":     "path_exists" | "taint_path",
                "action":   "<dom id>",
                "target":   "<dom id>",
                "passed":   bool,
                "evidence": [{"file": "...", "line": int}, ...],
                "reason":   str | None,     # only set when passed = false
                "query":    "<rendered .ql text>"
            },
            ...
        ]
    }

`checks` is empty for SKIP results. Frontend can render one panel per
entry so the user sees every check that ran (passing or failing),
the evidence rows CodeQL returned, and (optionally) the full QL.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .constraints.classifier import classify
from .constraints.types import ConstraintType
from .verifier import run_query, QUERIES_DIR


_SKIP_TYPES = {
    ConstraintType.API_CALL,
    ConstraintType.COUNTERFACTUAL,
    ConstraintType.LENGTH_MATCH,
    ConstraintType.ORDER,
}

_PATH_TYPES = {
    ConstraintType.PROBABILISTIC,
    ConstraintType.VALUE,
    ConstraintType.VALUE_WITH_DATAFLOW,
    ConstraintType.COMPOUND,
    ConstraintType.EXCLUSIVE,
}

_TAINT_TYPES = {
    ConstraintType.VALUE,
    ConstraintType.VALUE_WITH_DATAFLOW,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def stage1_check(ast: dict, db_path: str = "./codeql-db") -> dict:
    ctype = classify(ast)

    if ctype in _SKIP_TYPES:
        return _skip(f"{ctype.name} is future work — Stage 1 only covers UI-to-UI.")
    if _contains_api_ref(ast):
        return _skip("Constraint references call(api) or status(api); Stage 1 is UI-only.")
    if ctype not in _PATH_TYPES:
        return _skip(f"{ctype.name} not handled by Stage 1.")

    action_id = _action_id(ast)
    targets   = _target_ids(ast)
    if not action_id:
        return _skip("Could not extract the action element id from the AST.")
    if not targets:
        return _skip("Could not extract any target element id from the AST.")

    if not Path(db_path).is_dir():
        return {
            "result":  "FLAGGED",
            "reason":  f"CodeQL database not found at {db_path}. Rebuild it from the source.",
            "checks":  [],
        }

    checks: list[dict] = []

    # Check 1 — path existence for every target.
    for tid in targets:
        rows, query_text = _run_template("path_exists.ql",
                                         db_path=db_path,
                                         action_id=action_id,
                                         target_id=tid)
        passed = len(rows) > 0
        checks.append({
            "name":     "path_exists",
            "action":   action_id,
            "target":   tid,
            "passed":   passed,
            "evidence": rows,
            "reason":   None if passed
                        else f"no code path from handler({action_id}) to write({tid})",
            "query":    query_text,
        })

    # Check 2 — taint path only when the value_expr actually reads an element.
    if ctype in _TAINT_TYPES:
        for tid in targets:
            if not _value_expr_reads(ast, tid):
                continue
            rows, query_text = _run_template("taint_path.ql",
                                             db_path=db_path,
                                             action_id=action_id,
                                             target_id=tid)
            passed = len(rows) > 0
            checks.append({
                "name":     "taint_path",
                "action":   action_id,
                "target":   tid,
                "passed":   passed,
                "evidence": rows,
                "reason":   None if passed
                            else f"no taint path from {action_id} to {tid} — written value may not derive from user input",
                "query":    query_text,
            })

    failed = [c for c in checks if not c["passed"]]
    if failed:
        summary = "; ".join(c["reason"] for c in failed)
        return {"result": "FLAGGED", "reason": summary, "checks": checks}
    return {"result": "PASSED", "reason": None, "checks": checks}


# ---------------------------------------------------------------------------
# AST traversal helpers
# ---------------------------------------------------------------------------

def _action_id(ast: dict) -> str | None:
    return _first_action_element(ast.get("condition"))


def _first_action_element(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Action" and isinstance(node.get("element"), str):
        return node["element"]
    for v in node.values():
        if isinstance(v, (dict, list)):
            found = _first_action_element(v)
            if found:
                return found
    return None


def _target_ids(ast: dict) -> list[str]:
    out: list[str] = []
    _collect_writes(ast.get("event"), out)
    seen: set[str] = set()
    unique: list[str] = []
    for tid in out:
        if tid not in seen:
            seen.add(tid)
            unique.append(tid)
    return unique


def _collect_writes(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "WriteEvent" and isinstance(node.get("element"), str):
            out.append(node["element"])
        for v in node.values():
            _collect_writes(v, out)
    elif isinstance(node, list):
        for item in node:
            _collect_writes(item, out)


def _value_expr_reads(ast: dict, target_id: str) -> bool:
    for write in _all_writes_for(ast.get("event"), target_id):
        ve = write.get("value_expr")
        if ve and _expr_has_read(ve):
            return True
    return False


def _all_writes_for(node: Any, target_id: str) -> list[dict]:
    out: list[dict] = []
    if isinstance(node, dict):
        if (node.get("type") == "WriteEvent"
                and node.get("element") == target_id):
            out.append(node)
        for v in node.values():
            out.extend(_all_writes_for(v, target_id))
    elif isinstance(node, list):
        for item in node:
            out.extend(_all_writes_for(item, target_id))
    return out


def _expr_has_read(node: Any) -> bool:
    if isinstance(node, dict):
        t = node.get("type")
        if t in ("ReadExpr", "IncrementExpr", "FuncExpr"):
            return True
        if t == "LenExpr":
            return node.get("element") != "api_result"
        return any(_expr_has_read(v) for v in node.values())
    if isinstance(node, list):
        return any(_expr_has_read(item) for item in node)
    return False


def _contains_api_ref(ast: Any) -> bool:
    if isinstance(ast, dict):
        if ast.get("type") in ("CallEvent", "StatusExpr"):
            return True
        return any(_contains_api_ref(v) for v in ast.values())
    if isinstance(ast, list):
        return any(_contains_api_ref(item) for item in ast)
    return False


# ---------------------------------------------------------------------------
# CodeQL invocation
# ---------------------------------------------------------------------------

def _run_template(template_name: str, *, db_path: str, **subs: str) -> tuple[list[dict], str]:
    """
    Render *template_name* with *subs*, write the result alongside the
    qlpack so imports resolve, run it, return (rows, rendered_text).
    """
    template_path = QUERIES_DIR / template_name
    text = template_path.read_text()
    for key, value in subs.items():
        text = text.replace(f"__{key.upper()}__", value)

    instance_name = f"_rendered_{template_name}"
    rendered = QUERIES_DIR / instance_name
    rendered.write_text(text)
    try:
        rows = run_query(db_path, instance_name)
    finally:
        try:
            rendered.unlink()
        except FileNotFoundError:
            pass
    return rows, text


def _skip(reason: str) -> dict:
    return {"result": "SKIP", "reason": reason, "checks": []}
