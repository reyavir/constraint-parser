"""
Verification dispatcher — picks a strategy via the classifier.

`classify()` reduces the dict AST to a `ConstraintType`; this module routes
each variant to the appropriate checker. PROBABILISTIC is wired end-to-end
through `check_probabilistic`. The other branches are still stubs.

`run_codeql` wraps the CodeQL CLI for the static-analysis branches.
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

_FLOAT_TOL = 1e-6


def verify(
    ast: dict,
    traces: list[dict] | None = None,
    network_log: Any = None,
    db_path: str = "./codeql-db",
) -> dict[str, Any]:
    ctype = classify(ast)
    match ctype:
        case ConstraintType.PROBABILISTIC:
            return check_probabilistic(ast, traces or [])
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


# ─────────────────────────────────────────────────────────────────────────────
# Probabilistic checker
# ─────────────────────────────────────────────────────────────────────────────

def check_probabilistic(ast: dict, traces: list[dict]) -> dict:
    """
    Evaluate ``P(event | condition) op probability`` against a list of
    trace rollups produced by ``generate_traces_for_constraint``.

    Scoring is **trace-level**: each trace is one observation. A trace
    "satisfies" the condition if the condition action appears anywhere
    in the trace's ``triggered`` list, and "satisfies" the event if the
    event fires anywhere in the trace.

    Causal questions ("did the click *cause* the write?") are handled
    by Stage 1 / static CodeQL data-flow checks, not here. This
    function answers the outcome question: "in sessions that include
    A, what fraction also include B?"

    Returns:

        {
            "result":                "PASSED" | "FAILED" | "INCONCLUSIVE",
            "expected":              0.9,
            "operator":              ">=",
            "observed":              0.94,
            "samples_total":         100,
            "samples_condition_met": 50,
            "samples_event_met":     47,
            "reason":                None | "observed P = 0.40, expected = 1.0"
        }
    """
    expected = ast.get("probability")
    op       = ast.get("prob_operator", "=")

    if expected is None:
        return {
            "result":  "INCONCLUSIVE",
            "reason":  "AST has no probability value",
            "samples_total": len(traces),
        }

    n_total     = len(traces)
    n_condition = 0
    n_both      = 0
    failing_examples: list[dict] = []

    for tr in traces:
        if not _eval_condition(ast.get("condition"), tr):
            continue
        n_condition += 1
        if _eval_event(ast.get("event"), tr, condition=ast.get("condition")):
            n_both += 1
        else:
            if len(failing_examples) < 3:
                failing_examples.append({"id": tr.get("id"),
                                         "triggered": tr.get("triggered"),
                                         "written":   tr.get("written"),
                                         "written_values": tr.get("written_values"),
                                         "errors":    tr.get("errors", [])[:2]})

    if n_condition == 0:
        return {
            "result":                "INCONCLUSIVE",
            "reason":                "condition was never satisfied in any trace",
            "expected":              expected,
            "operator":              op,
            "samples_total":         n_total,
            "samples_condition_met": 0,
            "samples_event_met":     0,
        }

    observed = n_both / n_condition
    passed   = _compare(observed, op, expected)

    return {
        "result":                "PASSED" if passed else "FAILED",
        "expected":              expected,
        "operator":              op,
        "observed":              round(observed, 4),
        "samples_total":         n_total,
        "samples_condition_met": n_condition,
        "samples_event_met":     n_both,
        "reason":                None if passed
                                 else f"observed P = {observed:.4f}; expected {op} {expected}",
        "failing_examples":      failing_examples,
    }


# ── AST → boolean evaluators over a single trace ────────────────────────────

def _eval_condition(node: Any, trace: dict) -> bool:
    """
    Conditions in the current grammar are a single ``Action`` (possibly
    negated, possibly with a guard). Future grammar extensions (e.g.
    multi-action conditions) would extend this dispatch.
    """
    if not isinstance(node, dict):
        return False
    if node.get("type") != "Action":
        return False

    elem = node.get("element")
    triggered = elem in trace.get("triggered", [])
    if node.get("negated"):
        triggered = not triggered
    if not triggered:
        return False

    guard = node.get("guard")
    if guard:
        return _eval_guard(guard, trace, side="before")
    return True


def _eval_event(node: Any, trace: dict, condition: dict | None = None) -> bool:
    """
    Evaluate whether ``node`` (the event side of a probabilistic constraint)
    holds in *trace*.

    ``condition`` is the condition AST. It's used to make value-expression
    checks **phase-aware**: when the condition is a positive Action, we
    anchor ``r(x) + 1`` / ``r(x)`` / literal comparisons to *the state at
    the moment of that click*, not to trace start or trace end. For events
    without a value expression (plain ``w(x)``) the trace-level "did it
    happen at any point" check is used and ``condition`` is ignored.
    """
    if not isinstance(node, dict):
        return False
    t = node.get("type")

    if t == "WriteEvent":
        elem = node.get("element")
        if elem not in trace.get("written", []):
            return False
        ve = node.get("value_expr")
        if ve is None:
            return True
        action_elem = _condition_action_element(condition)
        if action_elem is not None:
            return _value_check_at_action(ve, target=elem,
                                          action_elem=action_elem,
                                          trace=trace)
        # No positive Action condition to anchor to — fall back to last-write.
        return _eval_value_expr(ve, trace,
                                observed=trace.get("written_values", {}).get(elem))

    if t == "CompoundEvent":
        op = node.get("op")
        l  = _eval_event(node.get("left"),  trace, condition)
        r  = _eval_event(node.get("right"), trace, condition)
        if op == "AND": return l and r
        if op == "OR":  return l or r
        if op == "XOR": return l != r
        return False

    if t == "CallEvent":
        api = node.get("api") or ""
        for n in trace.get("network", []):
            ep  = n.get("endpoint") or ""
            ref = n.get("api_ref")  or ""
            if api and (api == ep or api == ref or ep.endswith(api)):
                return True
        return False

    if t == "Guard":
        return _eval_guard(node, trace, side="after")

    return False


# ── Phase-aware value-check helpers ─────────────────────────────────────────

def _condition_action_element(condition: Any) -> str | None:
    """
    Return the action element id if the condition is a non-negated Action,
    else None. Negated and missing conditions return None — the caller
    falls back to last-write semantics in those cases.
    """
    if not isinstance(condition, dict):
        return None
    if condition.get("type") != "Action":
        return None
    if condition.get("negated"):
        return None
    elem = condition.get("element")
    return elem if isinstance(elem, str) else None


def _value_check_at_action(ve: dict, *, target: str, action_elem: str, trace: dict) -> bool:
    """
    Phase-aware value check:

      1. Find the *first* click on ``action_elem`` in the trace's event log.
      2. Scan forward from there to the next action event ("phase boundary").
      3. Within that window, find the first write to ``target``.
      4. Reconstruct the trace state immediately before the click by
         replaying every write that happened before it.
      5. Evaluate the value expression against that click-time state and
         compare to the actual written value.

    Returns False if no click on ``action_elem`` exists in the event log,
    or if no write to ``target`` happens before the next action click.
    """
    events = trace.get("events", []) or []

    click_idx = next(
        (i for i, e in enumerate(events)
         if e.get("type") == "action" and e.get("element") == action_elem),
        None,
    )
    if click_idx is None:
        # Condition matched via the dedup'd `triggered` list but no click
        # event found — shouldn't happen, but degrade safely.
        return _eval_value_expr(ve, trace,
                                observed=trace.get("written_values", {}).get(target))

    target_write = None
    for j in range(click_idx + 1, len(events)):
        e = events[j]
        if e.get("type") == "action":
            break  # next phase started; abandon search
        if e.get("type") == "write" and e.get("element") == target:
            target_write = e
            break
    if target_write is None:
        return False

    # Replay all writes before the click to reconstruct state-at-click.
    state_at_click: dict = dict(trace.get("values_before") or {})
    for k in range(click_idx):
        e = events[k]
        if e.get("type") == "write":
            state_at_click[e.get("element")] = e.get("value")

    # Synthetic trace view so _eval_value_expr resolves ReadExpr /
    # IncrementExpr / LenExpr against click-time state rather than
    # trace-start state.
    synthetic = {
        "values_before":  state_at_click,
        "written_values": {**state_at_click, target: target_write.get("value")},
    }
    return _eval_value_expr(ve, synthetic, observed=target_write.get("value"))


def _eval_value_expr(ve: dict, trace: dict, *, observed: Any) -> bool:
    """
    Compare an observed written value against a constraint's expected
    value expression. Conservative: cases we can't yet evaluate are
    treated as *matching* so we don't false-positive failures — the
    parent path_exists / write check still has to hold.
    """
    t = ve.get("type")
    if t == "LiteralExpr":
        return _values_equal(observed, ve.get("value"))
    if t == "ReadExpr":
        source = ve.get("element")
        snapshot = trace.get("values_before", {}).get(source)
        return _values_equal(observed, snapshot)
    if t == "IncrementExpr":
        source = ve.get("element")
        delta  = ve.get("delta") or 0
        before = trace.get("values_before", {}).get(source)
        try:
            return abs(float(observed) - (float(before) + float(delta))) < _FLOAT_TOL
        except (TypeError, ValueError):
            return False
    # FuncExpr, LenExpr, StatusExpr, BinaryExpr — not yet evaluated.
    return True


def _eval_guard(g: dict, trace: dict, *, side: str) -> bool:
    if g.get("type") != "Guard":
        return False
    l = _read_expr_value(g.get("left"),  trace, side=side)
    r = _read_expr_value(g.get("right"), trace, side=side)
    op = g.get("op")
    try:
        lf, rf = float(l), float(r)
        return _numeric_compare(lf, op, rf)
    except (TypeError, ValueError):
        return _string_compare(str(l), op, str(r))


def _read_expr_value(expr: Any, trace: dict, *, side: str) -> Any:
    if not isinstance(expr, dict):
        return None
    t = expr.get("type")
    if t == "LiteralExpr":
        v = expr.get("value")
        return None if v == "null" else v
    if t == "ReadExpr":
        elem = expr.get("element")
        if side == "before":
            return trace.get("values_before", {}).get(elem)
        # "after" — prefer the most recent write, fall back to snapshot.
        written = trace.get("written_values", {}).get(elem)
        return written if written is not None else trace.get("values_before", {}).get(elem)
    if t == "LenExpr":
        elem = expr.get("element")
        # Use the post-action value when measuring length of a UI element.
        target = trace.get("written_values", {}).get(elem)
        if target is None:
            target = trace.get("values_before", {}).get(elem)
        return len(target) if isinstance(target, str) else None
    return None


# ── primitive comparisons ───────────────────────────────────────────────────

def _values_equal(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a == b
    try:
        return abs(float(a) - float(b)) < _FLOAT_TOL
    except (TypeError, ValueError):
        return str(a) == str(b)


def _numeric_compare(l: float, op: str, r: float) -> bool:
    eq = abs(l - r) < _FLOAT_TOL
    if op == "=":  return eq
    if op == "<":  return l < r and not eq
    if op == ">":  return l > r and not eq
    if op == "<=": return l < r or eq
    if op == ">=": return l > r or eq
    return False


def _string_compare(l: str, op: str, r: str) -> bool:
    if op == "=":  return l == r
    if op == "<":  return l < r
    if op == ">":  return l > r
    if op == "<=": return l <= r
    if op == ">=": return l >= r
    return False


def _compare(observed: float, op: str, expected: float) -> bool:
    return _numeric_compare(float(observed), op, float(expected))


# ─────────────────────────────────────────────────────────────────────────────
# CodeQL plumbing for static-analysis checkers
# ─────────────────────────────────────────────────────────────────────────────

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
