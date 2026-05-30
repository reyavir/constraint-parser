"""
Explain *why* the classifier picked a given ConstraintType and *which*
static-analysis primitives the dispatcher will run as a result.

This module is purely descriptive — it doesn't change anything about
classification or dispatch. It mirrors the logic in classifier.py and
src/static_checks.py so the UI can show the user:

    classification_trace(ast):
        ordered list of branch checks the classifier evaluates, each
        annotated with whether it matched and which type it would have
        chosen if so. The first match wins; subsequent checks are
        skipped. Example for P(w(x) | A(y)) = 1:

            [
              {"rule": "event is CallEvent?",          "matched": False,
                                                       "would_give": "API_CALL"},
              {"rule": "condition is negated (¬A)?",   "matched": False,
                                                       "would_give": "COUNTERFACTUAL"},
              {"rule": "WriteEvent has value_expr?",   "matched": False,
                                                       "would_give": "VALUE / VALUE_WITH_DATAFLOW"},
              {"rule": "event is Guard?",              "matched": False,
                                                       "would_give": "GUARD"},
              {"rule": "event is CompoundEvent?",      "matched": False,
                                                       "would_give": "COMPOUND / EXCLUSIVE"},
              {"rule": "default — none of the above",  "matched": True,
                                                       "would_give": "PROBABILISTIC"},
            ]

    dispatch_plan(ast):
        list of primitive invocations the dispatcher will make, in the
        order they'll run, with their slot bindings:

            [
              {"primitive":   "path_exists",
               "query_file":  "queries/path_exists.ql",
               "description": "Is there a code path from the action's …",
               "slots":       {"ACTION_ID": "y", "TARGET_ID": "x"}},
            ]
"""

from __future__ import annotations

from typing import Any

from .classifier import classify
from .types      import ConstraintType


# ─────────────────────────────────────────────────────────────────────────────
# Classification trace
# ─────────────────────────────────────────────────────────────────────────────

def classification_trace(ast: dict) -> list[dict]:
    event = ast.get("event") or {}
    cond  = ast.get("condition") or {}

    steps: list[dict] = []
    # Each rule mirrors a branch in classifier.classify().

    is_call = event.get("type") == "CallEvent"
    steps.append({
        "rule":       "event is CallEvent?",
        "detail":     "checking ast.event.type == 'CallEvent'",
        "matched":    is_call,
        "would_give": "API_CALL",
    })
    if is_call:
        return _close(steps)

    is_neg = bool(cond.get("negated"))
    steps.append({
        "rule":       "condition is negated (¬A)?",
        "detail":     "checking ast.condition.negated",
        "matched":    is_neg,
        "would_give": "COUNTERFACTUAL",
    })
    if is_neg:
        return _close(steps)

    is_write_value = (event.get("type") == "WriteEvent"
                      and event.get("value_expr") is not None)
    steps.append({
        "rule":       "WriteEvent carries a value_expr (e.g. w(x, expr))?",
        "detail":     "checking ast.event.type == 'WriteEvent' and value_expr is not None",
        "matched":    is_write_value,
        "would_give": "VALUE  or  VALUE_WITH_DATAFLOW",
    })
    if is_write_value:
        ve_type = (event["value_expr"] or {}).get("type") or "?"
        # Sub-classification of the value_expr. Each row is one disjoint
        # group; the matched one decides VALUE vs VALUE_WITH_DATAFLOW.
        sub_groups = [
            ("value_expr is a literal constant (LiteralExpr)?",
             "LiteralExpr",
             {"LiteralExpr"},
             "VALUE"),
            ("value_expr is an external non-dataflow value (LenExpr / StatusExpr)?",
             "LenExpr | StatusExpr",
             {"LenExpr", "StatusExpr"},
             "VALUE"),
            ("value_expr references another element "
             "(ReadExpr / IncrementExpr / BinaryExpr)?",
             "ReadExpr | IncrementExpr | BinaryExpr",
             {"ReadExpr", "IncrementExpr", "BinaryExpr"},
             "VALUE_WITH_DATAFLOW"),
            ("value_expr is a function of an element (FuncExpr)?",
             "FuncExpr",
             {"FuncExpr"},
             "VALUE_WITH_DATAFLOW"),
        ]
        matched_any = False
        for rule_text, type_label, type_set, result in sub_groups:
            match = ve_type in type_set
            steps.append({
                "rule":       rule_text,
                "detail":     f"checking ast.event.value_expr.type ({ve_type!r}) "
                              f"in {{{type_label}}}",
                "matched":    match,
                "would_give": result,
                "indented":   True,
            })
            if match:
                matched_any = True
        if not matched_any:
            # Conservative default — unrecognised vexpr types still get
            # VALUE_WITH_DATAFLOW so we don't under-check by accident.
            steps.append({
                "rule":       "value_expr type is unrecognised — conservative fallback",
                "detail":     f"value_expr.type {ve_type!r} not in any known group",
                "matched":    True,
                "would_give": "VALUE_WITH_DATAFLOW (default)",
                "indented":   True,
            })
        return _close(steps)

    is_guard = event.get("type") == "Guard"
    steps.append({
        "rule":       "event is a Guard (e.g. len(r(x)) = len(r(y)))?",
        "detail":     "checking ast.event.type == 'Guard'",
        "matched":    is_guard,
        "would_give": "GUARD",
    })
    if is_guard:
        return _close(steps)

    is_compound = event.get("type") == "CompoundEvent"
    steps.append({
        "rule":       "event is a CompoundEvent (AND / OR / XOR)?",
        "detail":     "checking ast.event.type == 'CompoundEvent'",
        "matched":    is_compound,
        "would_give": "COMPOUND  (or EXCLUSIVE if op is XOR)",
    })
    if is_compound:
        op = event.get("op")
        steps.append({
            "rule":       f"compound op is XOR?  (op = {op})",
            "detail":     "XOR → EXCLUSIVE; AND / OR → COMPOUND",
            "matched":    op == "XOR",
            "would_give": "EXCLUSIVE" if op == "XOR" else "COMPOUND",
        })
        return _close(steps)

    steps.append({
        "rule":       "default — none of the above",
        "detail":     "no other branch matched",
        "matched":    True,
        "would_give": "PROBABILISTIC",
    })
    return _close(steps)


def _close(steps: list[dict]) -> list[dict]:
    """
    Mark un-matched steps as 'skipped' if they come after a matching
    step *at the same nesting level*. Top-level rules and indented
    sub-rules are tracked separately so a parent-level match doesn't
    silently dim every sub-rule under it.

    Skip rules:
      - A top-level step gets `skipped = True` if some earlier top-level
        step matched AND this one didn't.
      - An indented sub-step gets `skipped = True` if some earlier sub-step
        in the same scope matched AND this one didn't.
      - A new top-level step opens a fresh sub-rule scope.
      - A step that itself matched is NEVER marked skipped, regardless
        of what came before.
    """
    top_matched = False
    sub_matched = False
    for s in steps:
        indented = bool(s.get("indented"))
        if indented:
            if sub_matched and not s["matched"]:
                s["skipped"] = True
            if s["matched"]:
                sub_matched = True
        else:
            sub_matched = False        # new top-level scope
            if top_matched and not s["matched"]:
                s["skipped"] = True
            if s["matched"]:
                top_matched = True
    return steps


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch plan — which primitives will run, with their slot bindings
# ─────────────────────────────────────────────────────────────────────────────

# Keep in sync with src/static_checks.py:_PRIMITIVES_FOR_TYPE.
_PRIMITIVES_FOR_TYPE: dict[ConstraintType, list[str]] = {
    ConstraintType.PROBABILISTIC:        ["path_exists", "all_paths_write"],
    ConstraintType.VALUE:                ["path_exists", "literal_value", "all_paths_write"],
    ConstraintType.VALUE_WITH_DATAFLOW:  ["path_exists", "source_set", "self_increment",
                                          "api_result_taint", "all_paths_write"],
    ConstraintType.COMPOUND:             ["path_exists", "all_paths_write"],
    ConstraintType.EXCLUSIVE:            ["path_exists"],
    ConstraintType.COUNTERFACTUAL:       ["no_other_handlers"],
}

_PRIMITIVE_META: dict[str, dict] = {
    "path_exists": {
        "query_file":  "queries/path_exists.ql",
        "description": "Is there a code path from the action's event handler "
                       "to a write of the target element?",
        "slots":       ["ACTION_ID", "TARGET_ID"],
    },
    "no_path": {
        "query_file":  "queries/path_exists.ql  (inverted)",
        "description": "Same query as path_exists, but the verdict is inverted: "
                       "for P = 0 the path must NOT exist.",
        "slots":       ["ACTION_ID", "TARGET_ID"],
    },
    "literal_value": {
        "query_file":  "queries/literal_value.ql",
        "description": "Does the target write actually assign the specific literal k?",
        "slots":       ["ACTION_ID", "TARGET_ID", "LITERAL"],
    },
    "source_set": {
        "query_file":  "queries/all_sources_to_sink.ql",
        "description": "Does the written value derive from exactly the set of "
                       "elements the value_expr names? (no missing, no extras)",
        "slots":       ["TARGET_ID"],
    },
    "self_increment": {
        "query_file":  "queries/self_increment.ql",
        "description": "Does the write add a numeric literal (the “+ c” part of "
                       "an IncrementExpr)?",
        "slots":       ["ACTION_ID", "TARGET_ID"],
    },
    "all_paths_write": {
        "query_file":  "queries/all_paths_write.ql",
        "description": "Does EVERY code path through the action's handler reach a "
                       "write to the target? (universal / sufficient half of P = 1)",
        "slots":       ["ACTION_ID", "TARGET_ID"],
    },
    "api_result_taint": {
        "query_file":  "queries/api_result_taint.ql",
        "description": "Does the value written to the target taint-flow from an "
                       "API response parse (.json() / .text())?",
        "slots":       ["ACTION_ID", "TARGET_ID"],
    },
    "no_other_handlers": {
        "query_file":  "queries/other_handlers_reach.ql",
        "description": "Are any handlers OTHER than the action's reaching a "
                       "write on the target? PASS means none.",
        "slots":       ["ACTION_ID", "TARGET_ID"],
    },
    "guarded_write": {
        "query_file":  "queries/guarded_write.ql",
        "description": "Is the write to the target nested inside an `if` whose "
                       "condition reads the guard element?",
        "slots":       ["ACTION_ID", "TARGET_ID", "GUARD_ID"],
    },
}


def dispatch_plan(ast: dict) -> list[dict]:
    """List the primitive invocations the dispatcher will make, in order."""
    try:
        ctype = classify(ast)
    except Exception:
        return []

    primitives = list(_PRIMITIVES_FOR_TYPE.get(ctype, []))
    # path_exists gets reported as "no_path" when the constraint asserts
    # the event must never happen (mirrors _run_path_exists's inversion).
    if _expects_absence(ast) and "path_exists" in primitives:
        primitives = ["no_path" if p == "path_exists" else p for p in primitives]

    action_id = _action_id(ast)
    targets   = _target_ids(ast)

    plan: list[dict] = []
    for primitive in primitives:
        meta = _PRIMITIVE_META.get(primitive, {})
        for tid in targets:
            slots = _slot_values(primitive, ast, action_id, tid)
            applies = _primitive_applies(primitive, ast, tid)
            plan.append({
                "primitive":   primitive,
                "query_file":  meta.get("query_file"),
                "description": meta.get("description"),
                "target":      tid,
                "slots":       slots,
                "applies":     applies,
                "skip_reason": None if applies else _skip_reason(primitive, ast, tid),
            })

    # guarded_write fires whenever the condition has a guard (Row 5),
    # regardless of constraint type.
    if _condition_has_guard(ast):
        meta = _PRIMITIVE_META["guarded_write"]
        for tid in targets:
            slots = _slot_values("guarded_write", ast, action_id, tid)
            plan.append({
                "primitive":   "guarded_write",
                "query_file":  meta["query_file"],
                "description": meta["description"],
                "target":      tid,
                "slots":       slots,
                "applies":     True,
                "skip_reason": None,
            })

    return plan


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (kept tiny so they stay in sync with src/static_checks.py)
# ─────────────────────────────────────────────────────────────────────────────

def _slot_values(primitive: str, ast: dict, action_id: str | None,
                 target_id: str) -> dict:
    slots: dict[str, str] = {}
    needed = set(_PRIMITIVE_META.get(primitive, {}).get("slots", []))
    if "ACTION_ID" in needed and action_id:
        slots["ACTION_ID"] = action_id
    if "TARGET_ID" in needed:
        slots["TARGET_ID"] = target_id
    if "LITERAL" in needed:
        lit = _value_literal_for(ast, target_id)
        slots["LITERAL"] = "" if lit is None else str(lit)
    if "GUARD_ID" in needed:
        ids = _guard_read_elements(ast)
        slots["GUARD_ID"] = ids[0] if ids else (action_id or "")
    return slots


def _primitive_applies(primitive: str, ast: dict, target_id: str) -> bool:
    if primitive == "literal_value":
        return _value_literal_for(ast, target_id) is not None
    if primitive == "source_set":
        return bool(_value_read_elements(ast, target_id))
    if primitive == "self_increment":
        return _value_is_increment(ast, target_id)
    if primitive == "all_paths_write":
        return not _expects_absence(ast) and not _condition_has_guard(ast)
    if primitive == "api_result_taint":
        return _value_reads_api_result(ast, target_id)
    return True


def _skip_reason(primitive: str, ast: dict, target_id: str) -> str:
    if primitive == "literal_value":
        return "value_expr is not a LiteralExpr"
    if primitive == "source_set":
        return "value_expr doesn't read any element"
    if primitive == "self_increment":
        return "value_expr is not an IncrementExpr"
    if primitive == "all_paths_write":
        if _expects_absence(ast):
            return "constraint asserts absence (P = 0); no_path covers it soundly"
        return ("condition has a guard; universality is scoped to the guard "
                "branch, which `guarded_write` carries structurally")
    if primitive == "api_result_taint":
        return "value_expr doesn't reference api_result"
    return ""


def _action_id(ast: dict) -> str | None:
    cond = ast.get("condition")
    if isinstance(cond, dict) and cond.get("type") == "Action":
        e = cond.get("element")
        if isinstance(e, str):
            return e
    return None


def _target_ids(ast: dict) -> list[str]:
    out: list[str] = []
    _collect_writes(ast.get("event"), out)
    seen, unique = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _collect_writes(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "WriteEvent" and isinstance(node.get("element"), str):
            out.append(node["element"])
        for v in node.values():
            _collect_writes(v, out)
    elif isinstance(node, list):
        for x in node:
            _collect_writes(x, out)


def _value_expr_for(ast: dict, target_id: str):
    for w in _all_writes_for(ast.get("event"), target_id):
        ve = w.get("value_expr")
        if ve is not None:
            return ve
    return None


def _all_writes_for(node, target_id):
    out = []
    if isinstance(node, dict):
        if node.get("type") == "WriteEvent" and node.get("element") == target_id:
            out.append(node)
        for v in node.values():
            out.extend(_all_writes_for(v, target_id))
    elif isinstance(node, list):
        for x in node:
            out.extend(_all_writes_for(x, target_id))
    return out


def _value_literal_for(ast, target_id):
    ve = _value_expr_for(ast, target_id)
    if isinstance(ve, dict) and ve.get("type") == "LiteralExpr":
        return ve.get("value")
    return None


def _value_is_increment(ast, target_id) -> bool:
    ve = _value_expr_for(ast, target_id)
    return isinstance(ve, dict) and ve.get("type") == "IncrementExpr"


def _value_reads_api_result(ast, target_id) -> bool:
    ve = _value_expr_for(ast, target_id)
    return _references_api_result(ve)


def _references_api_result(node) -> bool:
    if isinstance(node, dict):
        if (node.get("type") in ("ReadExpr", "LenExpr")
                and node.get("element") == "api_result"):
            return True
        return any(_references_api_result(v) for v in node.values())
    if isinstance(node, list):
        return any(_references_api_result(item) for item in node)
    return False


def _value_read_elements(ast, target_id) -> list[str]:
    ve = _value_expr_for(ast, target_id)
    out: list[str] = []
    _collect_value_reads(ve, out)
    return list(dict.fromkeys(out))


def _collect_value_reads(node, out: list[str]) -> None:
    if isinstance(node, dict):
        if (node.get("type") in ("ReadExpr", "IncrementExpr", "LenExpr")
                and isinstance(node.get("element"), str)
                and node["element"] != "api_result"):
            out.append(node["element"])
        for v in node.values():
            _collect_value_reads(v, out)
    elif isinstance(node, list):
        for x in node:
            _collect_value_reads(x, out)


def _guard_read_elements(ast) -> list[str]:
    cond = ast.get("condition") or {}
    out: list[str] = []
    _collect_value_reads(cond.get("guard"), out)
    return list(dict.fromkeys(out))


def _condition_has_guard(ast) -> bool:
    cond = ast.get("condition") or {}
    return isinstance(cond, dict) and cond.get("guard") is not None


def _expects_absence(ast) -> bool:
    op = ast.get("prob_operator", "=")
    p  = ast.get("probability")
    if p is None: return False
    if op == "="  and p == 0: return True
    if op == "<=" and p == 0: return True
    if op == "<"  and p <= 0: return True
    return False
