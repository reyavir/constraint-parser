"""
Stage 1 — static (CodeQL-based) checks that run before any runtime tracing.

Five primitive queries currently live in queries/:

    path_exists.ql           a code path exists from the action's handler
                             to a write on the target element
    taint_path.ql            the value written to the target taint-flows
                             from a property read on the action
    all_sources_to_sink.ql   enumerates every element whose property read
                             taint-flows into the target write (used for
                             exclusivity)
    other_handlers_reach.ql  lists handlers OTHER than the action's whose
                             reach includes a write to the target (used
                             for counterfactual "only A writes target")
    guarded_write.ql         the target write inside the action's handler
                             sits inside an `if` whose condition reads
                             the action element

The dispatcher below picks which primitives to run for each constraint
type. The mapping table (_PRIMITIVES_FOR_TYPE) is the single source of
truth — adding a new constraint type means adding one row, not writing
a new check function.

Public entry point:
    stage1_check(ast, db_path) -> {
        "result":  "PASSED" | "FLAGGED" | "SKIP",
        "reason":  str | None,
        "checks":  [
            {
                "name":     "path_exists" | "taint_path" | "exclusive_source"
                            | "no_other_handlers" | "guarded_write",
                "action":   "<dom id>",
                "target":   "<dom id>",
                "passed":   bool,
                "evidence": [{...}, ...],
                "reason":   str | None,    # only set when passed = false
                "query":    "<rendered .ql text>"
            },
            ...
        ]
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .constraints.classifier import classify
from .constraints.types import ConstraintType
from .verifier import run_query, QUERIES_DIR


# ---------------------------------------------------------------------------
# Dispatch table — constraint type → list of primitives to run.
#
# Each primitive name corresponds to one .ql file in queries/ and one
# handler in _PRIMITIVE_RUNNERS below. Listing a primitive multiple times
# is fine; absent ones simply aren't run for that type.
# ---------------------------------------------------------------------------

_PRIMITIVES_FOR_TYPE: dict[ConstraintType, list[str]] = {
    # all_paths_write is the universal/sufficient half of P = 1: every
    # code path through the handler must dominate a write to the target.
    # It self-skips for P = 0 (no_path already covers absence soundly).
    # Not added to EXCLUSIVE (XOR is a runtime property; "every path
    # writes exactly one of two" isn't what path_exists carries) or to
    # COUNTERFACTUAL (no_other_handlers is already the universal check).
    ConstraintType.PROBABILISTIC:        ["path_exists", "all_paths_write"],
    ConstraintType.VALUE:                ["path_exists", "literal_value", "all_paths_write"],
    ConstraintType.VALUE_WITH_DATAFLOW:  ["path_exists", "source_set", "self_increment",
                                          "api_result_taint", "all_paths_write"],
    ConstraintType.COMPOUND:             ["path_exists", "all_paths_write"],
    # XOR-exclusivity ("exactly one of two targets fires") is a runtime
    # property — statically the most we can say is a path exists to each.
    ConstraintType.EXCLUSIVE:            ["path_exists"],
    ConstraintType.COUNTERFACTUAL:       ["no_other_handlers"],
}

# `guarded_write` (Row 5) is orthogonal to constraint type — it runs
# whenever the condition carries a guard, e.g. A(ei), r(ei) = v.

_SKIP_TYPES = {
    ConstraintType.API_CALL,
    ConstraintType.GUARD,
    ConstraintType.ORDER,
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

    primitives = _PRIMITIVES_FOR_TYPE.get(ctype)
    if not primitives:
        return _skip(f"{ctype.name} not handled by Stage 1 yet.")

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
    for primitive in primitives:
        runner = _PRIMITIVE_RUNNERS[primitive]
        for tid in targets:
            check = runner(ast=ast,
                           action_id=action_id,
                           target_id=tid,
                           db_path=db_path)
            if check is not None:
                checks.append(check)

    # Row 5 — orthogonal to type: if the condition carries a guard
    # (e.g. A(ei), r(ei) = v), also verify the write is structurally
    # gated by an if-statement that reads the action element.
    if _condition_has_guard(ast):
        for tid in targets:
            checks.append(_run_guarded_write(ast=ast,
                                             action_id=action_id,
                                             target_id=tid,
                                             db_path=db_path))

    failed = [c for c in checks if not c["passed"]]
    if failed:
        summary = "; ".join(c["reason"] for c in failed)
        return {"result": "FLAGGED", "reason": summary, "checks": checks}
    return {"result": "PASSED", "reason": None, "checks": checks}


# ---------------------------------------------------------------------------
# Primitive runners
#
# Each takes ast / action_id / target_id / db_path and returns either a
# check dict (with name, passed, evidence, reason, query) or None when
# the primitive doesn't apply to that target (e.g. taint_path skipped
# when the value_expr doesn't read an element).
# ---------------------------------------------------------------------------

def _run_path_exists(*, ast, action_id, target_id, db_path) -> dict:
    rows, query_text = _run_template("path_exists.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id)
    # Row 4: P(w(ej) | A(ei)) = 0 — "A taken, C should NOT update". Same
    # query, inverted verdict: a path existing is now a *violation*.
    if _expects_absence(ast):
        passed = len(rows) == 0
        return {
            "name":     "no_path",
            "action":   action_id,
            "target":   target_id,
            "passed":   passed,
            "evidence": rows,
            "reason":   None if passed
                        else f"handler({action_id}) DOES reach write({target_id}), "
                             f"but the constraint says it never should",
            "query":    query_text,
        }
    passed = len(rows) > 0
    return {
        "name":     "path_exists",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed
                    else f"no code path from handler({action_id}) to write({target_id})",
        "query":    query_text,
    }


def _run_literal_value(*, ast, action_id, target_id, db_path) -> dict | None:
    """
    Row C — P(w(ej, k) | A(ei)) = 1. Applies only when the value_expr is a
    literal. Verifies a write to the target (reachable from the action's
    handler) actually assigns that literal k. Self-skips otherwise.
    """
    lit = _value_literal_for(ast, target_id)
    if lit is None:
        return None
    rows, query_text = _run_template("literal_value.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id,
                                     literal=_ql_escape(str(lit)))
    passed = len(rows) > 0
    return {
        "name":     "literal_value",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed
                    else f"no write of literal {lit!r} to {target_id} reachable from handler({action_id})",
        "query":    query_text,
    }


def _run_source_set(*, ast, action_id, target_id, db_path) -> dict | None:
    """
    Rows 2 / 3 / D — verify the written value derives from EXACTLY the set
    of elements the value_expr names. Applies only when the value_expr
    reads at least one element. Self-skips otherwise.

    PASS iff the element sources reaching the write equal the expected set:
      - every expected element must flow in (the value uses what it claims)
      - no unexpected element may flow in (exclusivity / Row 3)
    """
    expected = set(_value_read_elements(ast, target_id))
    if not expected:
        return None
    rows, query_text = _run_template("all_sources_to_sink.ql",
                                     db_path=db_path,
                                     target_id=target_id)
    actual  = {r.get("source_id") for r in rows if r.get("source_id")}
    missing = sorted(expected - actual)
    extra   = sorted(actual - expected)
    passed  = not missing and not extra
    parts = []
    if missing:
        parts.append(f"value should derive from {missing} but no flow was found")
    if extra:
        parts.append(f"value also derives from unexpected element(s) {extra}")
    return {
        "name":     "source_set",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed else "; ".join(parts),
        "query":    query_text,
    }


def _run_api_result_taint(*, ast, action_id, target_id, db_path) -> dict | None:
    """
    Verify the value written to the target taint-flows from an API
    response parse (.json() / .text()). Self-skips unless the
    constraint's value_expr references api_result.
    """
    if not _value_reads_api_result(ast, target_id):
        return None
    rows, query_text = _run_template("api_result_taint.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id)
    passed = len(rows) > 0
    return {
        "name":     "api_result_taint",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed
                    else f"no taint path from an outgoing HTTP request response "
                         f"to the write of {target_id} in handler({action_id})",
        "query":    query_text,
    }


def _run_self_increment(*, ast, action_id, target_id, db_path) -> dict | None:
    """
    Row A — P(w(ej, r(ej) + c) | A(ei)) = 1. Applies only when the
    value_expr is an IncrementExpr. Verifies the write's expression adds
    a numeric literal (the "+ c"). The "reads ej" half is covered by the
    source_set check, which requires ej among the sources.
    """
    if not _value_is_increment(ast, target_id):
        return None
    rows, query_text = _run_template("self_increment.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id)
    passed = len(rows) > 0
    return {
        "name":     "self_increment",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed
                    else f"write({target_id}) in handler({action_id}) does not add a literal constant",
        "query":    query_text,
    }


def _run_all_paths_write(*, ast, action_id, target_id, db_path) -> dict | None:
    """
    Universal check — every code path through the handler reaches a
    write to the target. Self-skips in two cases:

      1. P = 0 constraints — `no_path` already covers absence soundly.
      2. Conditions carrying a guard (Row 5: P(w | A AND r(x) = v) = 1) —
         the universality claim is restricted to the guard's then-branch,
         not the whole handler. `guarded_write` carries the structural
         check; running all_paths_write on the entire handler would
         spuriously FLAG the else branch that legitimately doesn't write.
         A branch-aware all_paths_write is future work.
    """
    if _expects_absence(ast):
        return None
    if _condition_has_guard(ast):
        return None
    rows, query_text = _run_template("all_paths_write.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id)
    passed = len(rows) == 0
    return {
        "name":     "all_paths_write",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed
                    else f"some code path through handler({action_id}) exits "
                         f"without writing {target_id}",
        "query":    query_text,
    }


def _run_no_other_handlers(*, ast, action_id, target_id, db_path) -> dict:
    """
    Run other_handlers_reach. PASS iff the result set is empty — i.e. no
    handler other than action_id's reaches a write on the target.
    """
    rows, query_text = _run_template("other_handlers_reach.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id)
    offenders = sorted({r.get("other_handler_id") for r in rows if r.get("other_handler_id")})
    passed = len(rows) == 0
    return {
        "name":     "no_other_handlers",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed
                    else f"write({target_id}) is also reachable from handler(s): {', '.join(offenders)}",
        "query":    query_text,
    }


def _run_guarded_write(*, ast, action_id, target_id, db_path) -> dict:
    """
    Run guarded_write. PASS iff at least one guarded write was found —
    the write to the target is enclosed by an `if` reading the element
    the constraint's guard references (the action element for canonical
    Row 5, but the grammar permits any element).
    """
    guard_ids = _guard_read_elements(ast)
    guard_id  = guard_ids[0] if guard_ids else action_id
    rows, query_text = _run_template("guarded_write.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id,
                                     guard_id=guard_id)
    passed = len(rows) > 0
    return {
        "name":     "guarded_write",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed
                    else f"write({target_id}) in handler({action_id}) is not gated by an if-statement reading {guard_id}",
        "query":    query_text,
    }


def _guard_read_elements(ast: dict) -> list[str]:
    """Element ids read inside the condition's guard (ReadExpr/LenExpr nodes)."""
    cond  = ast.get("condition") or {}
    guard = cond.get("guard")
    out: list[str] = []
    _collect_read_elements(guard, out)
    seen, unique = set(), []
    for e in out:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def _collect_read_elements(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") in ("ReadExpr", "LenExpr") and isinstance(node.get("element"), str):
            if node["element"] != "api_result":
                out.append(node["element"])
        for v in node.values():
            _collect_read_elements(v, out)
    elif isinstance(node, list):
        for item in node:
            _collect_read_elements(item, out)


_PRIMITIVE_RUNNERS = {
    "path_exists":       _run_path_exists,
    "literal_value":     _run_literal_value,
    "source_set":        _run_source_set,
    "self_increment":    _run_self_increment,
    "api_result_taint":  _run_api_result_taint,
    "all_paths_write":   _run_all_paths_write,
    "no_other_handlers": _run_no_other_handlers,
    "guarded_write":     _run_guarded_write,
}


# ---------------------------------------------------------------------------
# AST traversal helpers
# ---------------------------------------------------------------------------

def _condition_has_guard(ast: dict) -> bool:
    cond = ast.get("condition") or {}
    return isinstance(cond, dict) and cond.get("guard") is not None


# ── value_expr inspection (for VALUE / VALUE_WITH_DATAFLOW dispatch) ─────────

def _value_expr_for(ast: dict, target_id: str):
    """The value_expr of the first WriteEvent targeting *target_id*, or None."""
    for write in _all_writes_for(ast.get("event"), target_id):
        ve = write.get("value_expr")
        if ve is not None:
            return ve
    return None


def _value_literal_for(ast: dict, target_id: str):
    """The literal value if the target's value_expr is a LiteralExpr, else None."""
    ve = _value_expr_for(ast, target_id)
    if isinstance(ve, dict) and ve.get("type") == "LiteralExpr":
        return ve.get("value")
    return None


def _value_is_increment(ast: dict, target_id: str) -> bool:
    ve = _value_expr_for(ast, target_id)
    return isinstance(ve, dict) and ve.get("type") == "IncrementExpr"


def _value_reads_api_result(ast: dict, target_id: str) -> bool:
    """True iff the target's value_expr contains a ReadExpr / LenExpr
    referencing api_result anywhere in its tree."""
    ve = _value_expr_for(ast, target_id)
    return _expr_references_api_result(ve)


def _expr_references_api_result(node: Any) -> bool:
    if isinstance(node, dict):
        if (node.get("type") in ("ReadExpr", "LenExpr")
                and node.get("element") == "api_result"):
            return True
        return any(_expr_references_api_result(v) for v in node.values())
    if isinstance(node, list):
        return any(_expr_references_api_result(item) for item in node)
    return False


def _value_read_elements(ast: dict, target_id: str) -> list[str]:
    """Distinct element ids read anywhere inside the target's value_expr."""
    ve = _value_expr_for(ast, target_id)
    out: list[str] = []
    _collect_value_elements(ve, out)
    seen, unique = set(), []
    for e in out:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def _collect_value_elements(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        if (node.get("type") in ("ReadExpr", "IncrementExpr", "LenExpr")
                and isinstance(node.get("element"), str)
                and node["element"] != "api_result"):
            out.append(node["element"])
        for v in node.values():
            _collect_value_elements(v, out)
    elif isinstance(node, list):
        for item in node:
            _collect_value_elements(item, out)


def _ql_escape(s: str) -> str:
    """Escape a value for safe substitution into a QL double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _expects_absence(ast: dict) -> bool:
    """
    True when the constraint asserts the event should *never* happen —
    i.e. the expected probability is pinned at zero. Used to invert
    path-existence verdicts (Row 4: P(w | A) = 0).
    """
    op = ast.get("prob_operator", "=")
    p  = ast.get("probability")
    if p is None:
        return False
    if op == "=" and p == 0:
        return True
    if op == "<=" and p == 0:
        return True
    if op == "<" and p <= 0:
        return True
    return False


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
