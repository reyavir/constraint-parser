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
from .mapping.pipeline import MAPPING_FILE
from .verifier import run_query, QUERIES_DIR


# ---------------------------------------------------------------------------
# Mapping helpers — used to route storage-target constraints to the right
# query sinks. A target id that lives in mapping.storage is a storage
# entry (localStorage / sessionStorage); everything else is a DOM element.
# ---------------------------------------------------------------------------

def _safe_load_mapping() -> dict:
    """Read element_mapping.json if present; tolerate any error silently."""
    try:
        import json
        if MAPPING_FILE.exists():
            with MAPPING_FILE.open() as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _dataset_keys_substitution(action_id: str, mapping: dict) -> str:
    """
    Build the QL list-literal contents that ``__DATASET_KEYS__`` substitutes
    to in the registeredViaBodyDelegation disjunct. The action element's
    data-* attribute names (camelCased) plus a no-match sentinel so the
    substitution is always non-empty — CodeQL rejects empty `[]` literals.

    Example: an element with ``data-add`` and ``data-q`` → ``"add", "q"``
    plus the sentinel. An element with no data-* attributes → just the
    sentinel, meaning the body-delegation disjunct effectively never fires.
    """
    entry = (mapping.get("elements") or {}).get(action_id) or {}
    keys = entry.get("data_attrs") or []
    safe = [k for k in keys if isinstance(k, str) and k]
    safe.append("__cv_no_match__")
    return ", ".join(f'"{_ql_escape(k)}"' for k in safe)


def _storage_key_for(target_id: str, mapping: dict) -> str:
    """Return the storage key for *target_id* if it's a storage entry,
    else the empty string (which the CodeQL queries treat as "no
    storage sink to match")."""
    entry = (mapping.get("storage") or {}).get(target_id) or {}
    key = entry.get("key")
    return key if isinstance(key, str) else ""


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

# For `P=0` ("the event never matches"), we run only the SHARPEST primitive
# that captures the full event predicate, with its verdict inverted. Running
# the regular =1 conjunction is wrong for two reasons:
#   - Several primitives have no inversion code and demand rows > 0,
#     which is exactly the thing =0 says shouldn't exist.
#   - For valued writes, the broader primitives (path_exists) over-flag.
#     Example: `P(w(t, "0") | A) = 0` and A writes t = 5 — the constraint
#     is satisfied (no write of literal 0 occurred) but path_exists sees
#     the write of 5 and, inverted, flags. The sharpest primitive
#     (literal_value) correctly returns 0 rows and, inverted, passes.
# Guard + =0 is handled separately in `_evaluate_event_leaf` — guarded_write
# alone is the sharpest check there.
# Only the per-leaf constraint types appear here. COMPOUND/EXCLUSIVE/
# COUNTERFACTUAL are top-level classifications that are either routed away
# before the walker (counterfactual → no_other_handlers) or have their
# leaves reclassified in `_evaluate_event_leaf` (compound/exclusive).
_NEGATION_PRIMITIVES_FOR_TYPE: dict[ConstraintType, list[str]] = {
    ConstraintType.PROBABILISTIC:        ["path_exists"],
    ConstraintType.VALUE:                ["literal_value"],
    ConstraintType.VALUE_WITH_DATAFLOW:  ["source_set", "self_increment",
                                          "api_result_taint"],
}

# `guarded_write` (Row 5) is orthogonal to constraint type — it runs
# whenever the condition carries a guard, e.g. A(ei), r(ei) = v.

_SKIP_TYPES = set()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def stage1_check(ast: dict, db_path: str = "./codeql-db") -> dict:
    ctype = classify(ast)

    if ctype in _SKIP_TYPES:
        return _skip(f"{ctype.name} is future work — Stage 1 only covers UI-to-UI.")

    # `persist(target)` is composite — split into save side (action writes
    # storage) + restore side (page-load reads storage). Dispatch early
    # so we don't try to fit it into the normal primitive pipeline.
    if ctype == ConstraintType.PERSIST:
        return _run_persist_check(ast, db_path)

    # `P(call(api) | A(action))` — handler-to-call reachability via the
    # call_reaches primitive. Negation flip is the same shape as Row 4
    # (zero rows = PASS for `= 0`).
    if ctype == ConstraintType.API_CALL:
        return _run_api_call_check(ast, db_path)

    # Other API references (StatusExpr or call inside a non-API_CALL
    # constraint) remain unsupported until runtime arrives.
    if _contains_api_ref(ast):
        return _skip("Constraint references status(api); Stage 1 is UI-only.")

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

    # Load mapping once so each runner can ask whether a target is a
    # storage entry and, if so, what its localStorage / sessionStorage
    # key is. Empty mapping is treated as "all targets are DOM."
    mapping = _safe_load_mapping()

    # Compute the dataset-keys substitution for the body-delegation
    # disjunct of registeredHandler. Threaded through every per-action
    # query call so the queries can recognise
    # `document.addEventListener('click', e => { if (e.target.dataset.X) {...} })`
    # binding patterns and tie them to specific element ids.
    dataset_keys = _dataset_keys_substitution(action_id, mapping)

    # Precheck: did our static analysis actually find any handler for
    # this action? Body-delegated handlers (document.addEventListener)
    # and `.onclick = fn` assignments are not yet recognised; running
    # primitives against an empty handler set produces misleading
    # PASS verdicts (notably all_paths_write passes vacuously when there
    # are no exits to enumerate). SKIP early with a clear reason.
    handler_rows, handler_query = _run_template(
        "handler_exists.ql",
        db_path=db_path,
        action_id=action_id,
        dataset_keys=dataset_keys)
    if not handler_rows:
        # For synthetic lifecycle actions (page-load), a missing handler IS
        # the bug we're asserting against — flag instead of skip.
        if action_id == "page-load":
            return {
                "result":  "FLAGGED",
                "reason":  ("no page-load handler found (no "
                            "window.addEventListener('load'), "
                            "document.addEventListener('DOMContentLoaded'), "
                            "or window.onload = fn)"),
                "checks":  [{
                    "name":     "handler_exists",
                    "action":   action_id,
                    "target":   None,
                    "passed":   False,
                    "evidence": [],
                    "reason":   "no page-load handler found",
                    "query":    handler_query,
                }],
            }
        return {
            "result":  "SKIP",
            "reason":  (f"No addEventListener handler recognised for "
                        f"A({action_id}). Recognised patterns: "
                        f"`getElementById('{action_id}').addEventListener(...)` "
                        f"and `querySelectorAll('.cls').forEach(el => "
                        f"el.addEventListener(...))`. Body-delegated handlers "
                        f"(document.addEventListener) and `.onclick = fn` "
                        f"assignments are not recognised."),
            "checks":  [{
                "name":     "handler_exists",
                "action":   action_id,
                "target":   None,
                "passed":   False,
                "evidence": [],
                "reason":   f"no handler recognised for A({action_id})",
                "query":    handler_query,
            }],
        }

    # Operator-aware evaluation: walk the event AST and combine per-leaf
    # results according to AND / OR / XOR semantics. For a single-atom
    # event side (no CompoundEvent), this collapses to the same behaviour
    # as the old conjunctive loop — every primitive must pass for the
    # one leaf. Guard checks (when the condition carries a guard) are
    # threaded INTO the walker so each leaf carries its own guard verdict;
    # this lets the operator semantics control guard aggregation too
    # (e.g. OR passes if at least one leaf's write AND guard both pass).
    event_node = ast.get("event") or {}
    has_guard  = _condition_has_guard(ast)
    tree_result = _evaluate_event_subtree(
        event_node, ast=ast, action_id=action_id,
        mapping=mapping, dataset_keys=dataset_keys, db_path=db_path,
        has_guard=has_guard)
    checks: list[dict] = list(tree_result["checks"])

    if tree_result["passed"]:
        return {"result": "PASSED", "reason": None, "checks": checks}
    failed = [c for c in checks if not c["passed"]]
    summary = "; ".join(c["reason"] for c in failed if c.get("reason"))
    return {"result": "FLAGGED", "reason": summary, "checks": checks}


def _evaluate_event_subtree(node: dict, *, ast: dict, action_id: str,
                             mapping: dict, dataset_keys: str,
                             db_path: str, has_guard: bool = False) -> dict:
    """
    Recursively evaluate an event-side subtree, respecting the AST's
    logical operator structure. Returns {"passed": bool, "checks": [...]}.

    For a CompoundEvent node, recurses on each operand and combines
    children's passed-verdicts according to the operator:
        AND   — every child must pass
        OR    — at least one child must pass
        XOR   — exactly one child must pass

    For a leaf event (WriteEvent, CallEvent, PersistEvent), runs the
    appropriate primitive set for that leaf's shape and aggregates
    conjunctively across primitives (every primitive must pass for the
    leaf to pass).

    The recursive verdict respects nested compounds — e.g.
    `w(a) AND (w(b) OR w(c))` correctly requires `a` and (`b` or `c`).
    """
    ntype = node.get("type")

    if ntype == "NotEvent":
        child = node.get("child")
        if not isinstance(child, dict):
            return {"passed": False, "checks": []}
        child_result = _evaluate_event_subtree(
            child, ast=ast, action_id=action_id,
            mapping=mapping, dataset_keys=dataset_keys, db_path=db_path,
            has_guard=has_guard)
        return {"passed": not child_result["passed"], "checks": child_result["checks"]}

    if ntype == "CompoundEvent":
        op = node.get("op", "AND")
        sub_results: list[dict] = []
        for child_key in ("left", "right"):
            child = node.get(child_key)
            if not isinstance(child, dict):
                continue
            sub_results.append(_evaluate_event_subtree(
                child, ast=ast, action_id=action_id,
                mapping=mapping, dataset_keys=dataset_keys, db_path=db_path,
                has_guard=has_guard))
        all_checks: list[dict] = []
        for r in sub_results:
            all_checks.extend(r["checks"])
        if op == "AND":
            passed = all(r["passed"] for r in sub_results) if sub_results else True
        elif op == "OR":
            passed = any(r["passed"] for r in sub_results) if sub_results else False
        elif op == "XOR":
            passed = sum(1 for r in sub_results if r["passed"]) == 1
        else:
            passed = all(r["passed"] for r in sub_results)
        return {"passed": passed, "checks": all_checks}

    # Leaf event — classify its shape, run its primitive set.
    return _evaluate_event_leaf(
        node, ast=ast, action_id=action_id,
        mapping=mapping, dataset_keys=dataset_keys, db_path=db_path,
        has_guard=has_guard)


def _evaluate_event_leaf(leaf: dict, *, ast: dict, action_id: str,
                          mapping: dict, dataset_keys: str,
                          db_path: str, has_guard: bool = False) -> dict:
    """
    Evaluate a single atomic event leaf (WriteEvent / CallEvent /
    PersistEvent / Guard) and return {"passed", "checks"}. Conjunctive
    across primitives — every primitive that applies to the leaf must
    pass for the leaf to pass.
    """
    ntype = leaf.get("type")

    # Counterfactual (¬A on condition side) is detected once from the
    # top-level ast — the walker keeps the same ast for every leaf, so
    # this stays consistent across recursion.
    is_counterfactual = bool((ast.get("condition") or {}).get("negated"))

    # CallEvent / PersistEvent leaves under counterfactual don't have a
    # well-defined semantics in the current implementation — the composite
    # runners (_run_api_call_check, _run_persist_check) don't consult the
    # counterfactual flag. SKIP with a clear reason instead of silently
    # producing a wrong verdict.
    if is_counterfactual and ntype in ("CallEvent", "PersistEvent"):
        return {
            "passed": False,
            "checks": [{
                "name":     "counterfactual_unsupported_leaf",
                "action":   action_id,
                "target":   leaf.get("api") or leaf.get("element"),
                "passed":   False,
                "evidence": [],
                "reason":   (f"counterfactual (¬A) constraints with {ntype!r} "
                             f"leaves are not supported — only WriteEvent leaves "
                             f"can appear under ¬A. Consider splitting into "
                             f"separate constraints."),
                "query":    "",
            }],
        }

    # CallEvent leaf — route to the same machinery as a top-level call
    # constraint, but with a per-leaf AST so the runner sees just this
    # CallEvent as ast.event.
    if ntype == "CallEvent":
        leaf_ast = dict(ast)
        leaf_ast["event"] = leaf
        leaf_result = _run_api_call_check(leaf_ast, db_path)
        leaf_checks = list(leaf_result.get("checks") or [])
        passed = leaf_result.get("result") == "PASSED"
        if has_guard:
            # No DOM target for the guard check; guards on calls aren't
            # meaningful structurally, so skip the guard layer here.
            pass
        return {"passed": passed, "checks": leaf_checks}

    # PersistEvent leaf — route to the persist composite (save + restore).
    if ntype == "PersistEvent":
        leaf_ast = dict(ast)
        leaf_ast["event"] = leaf
        leaf_result = _run_persist_check(leaf_ast, db_path)
        leaf_checks = list(leaf_result.get("checks") or [])
        passed = leaf_result.get("result") == "PASSED"
        return {"passed": passed, "checks": leaf_checks}

    if ntype != "WriteEvent":
        # Unknown leaf type — treat as failing with a clear message.
        return {
            "passed": False,
            "checks": [{
                "name":     "compound_leaf_unknown",
                "action":   action_id,
                "target":   None,
                "passed":   False,
                "evidence": [],
                "reason":   f"unsupported leaf node type {ntype!r} inside event tree.",
                "query":    "",
            }],
        }

    target = leaf.get("element")
    if not isinstance(target, str):
        return {
            "passed": False,
            "checks": [{
                "name":     "compound_leaf_invalid",
                "action":   action_id,
                "target":   None,
                "passed":   False,
                "evidence": [],
                "reason":   "WriteEvent leaf missing target element id.",
                "query":    "",
            }],
        }
    storage_key = _storage_key_for(target, mapping)

    # Decide the leaf's primitive set from its shape. Mirrors classify():
    #   bare w(t)                                 → PROBABILISTIC primitives
    #   w(t, literal)                             → VALUE primitives
    #   w(t, expr with reads) / w(t, sources={…}) → VALUE_WITH_DATAFLOW primitives
    if leaf.get("value_expr") is not None:
        leaf_type = _classify_value_expr_local(leaf["value_expr"])
    elif leaf.get("sources") is not None:
        leaf_type = ConstraintType.VALUE_WITH_DATAFLOW
    else:
        leaf_type = ConstraintType.PROBABILISTIC

    # Counterfactual (¬A) overrides the shape-based dispatch: every
    # WriteEvent leaf runs only no_other_handlers, asking whether any
    # handler other than the named action reaches a write to this leaf's
    # target. The walker's AND/OR/XOR/NOT combining then aggregates
    # per-leaf verdicts as usual.
    negate = _expects_absence(ast)
    if is_counterfactual:
        primitive_names: list[str] = ["no_other_handlers"]
    elif negate and has_guard:
        primitive_names = []
    elif negate:
        primitive_names = _NEGATION_PRIMITIVES_FOR_TYPE.get(leaf_type) or []
    else:
        primitive_names = _PRIMITIVES_FOR_TYPE.get(leaf_type) or []

    # Build a per-leaf AST so primitive runners that introspect the AST
    # (e.g. source_set walking the value_expr) see THIS leaf, not the
    # whole compound event.
    leaf_ast = dict(ast)
    leaf_ast["event"] = leaf

    leaf_checks: list[dict] = []
    for primitive_name in primitive_names:
        runner = _PRIMITIVE_RUNNERS.get(primitive_name)
        if runner is None:
            continue
        check = runner(ast=leaf_ast,
                       action_id=action_id,
                       target_id=target,
                       storage_key=storage_key,
                       dataset_keys=dataset_keys,
                       db_path=db_path)
        if check is not None:
            leaf_checks.append(check)

    # If the condition carries a guard, also run guarded_write per leaf
    # so the guard verdict combines with the operator (OR aggregates
    # over leaf-with-guard verdicts, not over guard checks separately).
    # For =0 this is the ONLY primitive that runs — see the negate+guard
    # branch above which clears primitive_names. Skipped for counterfactual
    # because ¬A + guard doesn't have a well-defined semantics yet.
    if has_guard and not is_counterfactual:
        gc = _run_guarded_write(ast=leaf_ast,
                                action_id=action_id,
                                target_id=target,
                                storage_key=storage_key,
                                dataset_keys=dataset_keys,
                                db_path=db_path)
        leaf_checks.append(gc)

    leaf_passed = all(c["passed"] for c in leaf_checks) if leaf_checks else True
    return {"passed": leaf_passed, "checks": leaf_checks}


def _classify_value_expr_local(value_expr: dict) -> "ConstraintType":
    """Same logic as classifier._classify_value_expr: VALUE vs VALUE_WITH_DATAFLOW
    depending on whether the value derives from element reads."""
    if _expr_has_read(value_expr) or _expr_has_increment(value_expr):
        return ConstraintType.VALUE_WITH_DATAFLOW
    return ConstraintType.VALUE


def _expr_has_increment(node) -> bool:
    if isinstance(node, dict):
        if node.get("type") == "IncrementExpr":
            return True
        return any(_expr_has_increment(v) for v in node.values())
    if isinstance(node, list):
        return any(_expr_has_increment(item) for item in node)
    return False


# ---------------------------------------------------------------------------
# Primitive runners
#
# Each takes ast / action_id / target_id / db_path and returns either a
# check dict (with name, passed, evidence, reason, query) or None when
# the primitive doesn't apply to that target (e.g. taint_path skipped
# when the value_expr doesn't read an element).
# ---------------------------------------------------------------------------

def _run_api_call_check(ast: dict, db_path: str) -> dict:
    """
    Dispatcher for `P(call(api[, expr]) | A(action))` constraints.

    Bare `call(api)`            → call_reaches (handler-to-call
                                  reachability).
    `call(api, r(x) [...])`     → call_with_source (subset check —
                                  is x's value used in any of the
                                  call's arguments?).
    """
    if not Path(db_path).is_dir():
        return {
            "result":  "FLAGGED",
            "reason":  f"CodeQL database not found at {db_path}.",
            "checks":  [],
        }

    action_id = _action_id(ast)
    api_name  = _api_name(ast)
    if not action_id:
        return _skip("call() constraint missing action id.")
    if not api_name:
        return _skip("call() constraint missing API name.")

    mapping      = _safe_load_mapping()
    dataset_keys = _dataset_keys_substitution(action_id, mapping)
    expects_zero = _expects_absence(ast)

    # If the CallEvent carries a value_expr whose source we can name,
    # route to call_with_source — subset check that the named source
    # actually flows into one of the call's arguments. Otherwise fall
    # back to the bare reachability check.
    source_ids = _api_call_source_elements(ast)
    if source_ids:
        return _run_call_with_source(
            ast=ast, action_id=action_id, api_name=api_name,
            source_ids=source_ids, dataset_keys=dataset_keys,
            expects_zero=expects_zero, db_path=db_path)

    rows, query_text = _run_template(
        "call_reaches.ql",
        db_path=db_path,
        action_id=action_id,
        api_name=api_name,
        dataset_keys=dataset_keys)

    if expects_zero:
        passed = len(rows) == 0
        reason = (None if passed
                  else f"handler({action_id}) DOES reach call({api_name}), "
                       f"but the constraint says it never should")
    else:
        passed = len(rows) > 0
        reason = (None if passed
                  else f"no code path from handler({action_id}) to "
                       f"call({api_name})")

    check = {
        "name":     "call_reaches",
        "action":   action_id,
        "target":   api_name,
        "passed":   passed,
        "evidence": rows,
        "reason":   reason,
        "query":    query_text,
    }
    return {
        "result":  "PASSED" if passed else "FLAGGED",
        "reason":  None if passed else reason,
        "checks":  [check],
    }


def _run_call_with_source(*, ast, action_id, api_name, source_ids,
                          dataset_keys, expects_zero, db_path) -> dict:
    """
    For each named source id, run call_with_source.ql and aggregate.
    Multiple sources are checked independently — `call(api, r(x) + r(y))`
    requires BOTH x and y to flow into the call (each must produce
    at least one row).
    """
    checks: list[dict] = []
    all_passed = True

    for src_id in source_ids:
        rows, query_text = _run_template(
            "call_with_source.ql",
            db_path=db_path,
            action_id=action_id,
            api_name=api_name,
            source_id=src_id,
            dataset_keys=dataset_keys)

        if expects_zero:
            passed = len(rows) == 0
            reason = (None if passed
                      else f"r({src_id}) DOES flow into call({api_name}) "
                           f"inside handler({action_id}), but the "
                           f"constraint says it never should")
        else:
            passed = len(rows) > 0
            reason = (None if passed
                      else f"no taint flow from r({src_id}) to any "
                           f"argument of call({api_name}) reachable from "
                           f"handler({action_id})")

        checks.append({
            "name":     "call_with_source",
            "action":   action_id,
            "target":   api_name,
            "passed":   passed,
            "evidence": rows,
            "reason":   reason,
            "query":    query_text,
        })
        if not passed:
            all_passed = False

    if all_passed:
        return {"result": "PASSED", "reason": None, "checks": checks}
    summary = "; ".join(c["reason"] for c in checks if not c["passed"])
    return {"result": "FLAGGED", "reason": summary, "checks": checks}


def _api_call_source_elements(ast: dict) -> list[str]:
    """Element ids read inside the CallEvent's value_expr (if any)."""
    event = ast.get("event") or {}
    if event.get("type") != "CallEvent":
        return []
    ve = event.get("params")
    if not ve:
        return []
    out: list[str] = []
    _collect_expr_reads(ve, out)
    seen, unique = set(), []
    for e in out:
        if e and e not in seen and e != "api_result":
            seen.add(e)
            unique.append(e)
    return unique


def _collect_expr_reads(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "ReadExpr" and isinstance(node.get("element"), str):
            out.append(node["element"])
        for v in node.values():
            _collect_expr_reads(v, out)
    elif isinstance(node, list):
        for item in node:
            _collect_expr_reads(item, out)


def _api_name(ast: dict) -> str | None:
    """Extract the api name from the first CallEvent in the event side."""
    return _first_api_in(ast.get("event"))


def _first_api_in(node: Any) -> str | None:
    if isinstance(node, dict):
        if node.get("type") == "CallEvent" and isinstance(node.get("api"), str):
            return node["api"]
        for v in node.values():
            found = _first_api_in(v)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _first_api_in(item)
            if found:
                return found
    return None


def _run_persist_check(ast: dict, db_path: str) -> dict:
    """
    Run the two-part persist check for `persist(target) | A(action)`:

      Save side    — path_exists from action's handler reaches a write
                     to the named storage entry. Reuses the existing
                     path_exists primitive.
      Restore side — at least one page-load handler reads the same
                     storage key. Uses the new page_load_restores
                     primitive.

    PASS iff both halves pass. The result reason makes clear which half
    failed so the constraint author knows whether to add the save call
    in their handler or wire up a page-load restore listener.
    """
    if not Path(db_path).is_dir():
        return {
            "result":  "FLAGGED",
            "reason":  f"CodeQL database not found at {db_path}.",
            "checks":  [],
        }

    action_id = _action_id(ast)
    targets   = _target_ids(ast)
    if not action_id or not targets:
        return _skip("persist constraint missing action or target id.")
    target_id = targets[0]

    mapping     = _safe_load_mapping()
    storage_key = _storage_key_for(target_id, mapping)
    if not storage_key:
        return {
            "result":  "FLAGGED",
            "reason":  (f"persist({target_id}): no storage entry named "
                        f"'{target_id}' found in the mapping (run Scan IDs "
                        f"and confirm the app calls "
                        f"localStorage.setItem(...) with a recognisable key)."),
            "checks":  [],
        }

    dataset_keys = _dataset_keys_substitution(action_id, mapping)

    save_check = _run_path_exists(
        ast=ast, action_id=action_id, target_id=target_id,
        storage_key=storage_key, dataset_keys=dataset_keys, db_path=db_path)
    save_check["name"] = "persist_save"

    # For `persist(s) = 0` — "this storage entry is never persisted by this
    # action" — only the save side carries a meaningful verdict. The restore
    # side asks a question about page-load behaviour that the =0 assertion
    # doesn't constrain ("never persist" says nothing about whether a load
    # handler reads the key), so running it would tank an otherwise-correct
    # verdict whenever the app has no restore wiring. _run_path_exists
    # already inverts for =0, so save_check.passed already means "no save
    # was reachable" — exactly the =0 assertion.
    if _expects_absence(ast):
        checks = [save_check]
        if save_check["passed"]:
            return {"result": "PASSED", "reason": None, "checks": checks}
        return {
            "result":  "FLAGGED",
            "reason":  save_check.get("reason") or "",
            "checks":  checks,
        }

    restore_rows, restore_query = _run_template(
        "page_load_restores.ql",
        db_path=db_path,
        storage_key=storage_key)
    restore_passed = len(restore_rows) > 0
    restore_check = {
        "name":     "persist_restore",
        "action":   "page-load",
        "target":   target_id,
        "passed":   restore_passed,
        "evidence": restore_rows,
        "reason":   None if restore_passed
                    else (f"no page-load handler reads storage key "
                          f"'{storage_key}' (need window.addEventListener"
                          f"('load'/'DOMContentLoaded') or window.onload "
                          f"that calls localStorage.getItem('{storage_key}'))"),
        "query":    restore_query,
    }
    checks = [save_check, restore_check]
    failed = [c for c in checks if not c["passed"]]
    if failed:
        return {
            "result":  "FLAGGED",
            "reason":  "; ".join(c["reason"] for c in failed),
            "checks":  checks,
        }
    return {"result": "PASSED", "reason": None, "checks": checks}


def _run_path_exists(*, ast, action_id, target_id, storage_key, dataset_keys, db_path) -> dict:
    rows, query_text = _run_template("path_exists.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id,
                                     storage_key=storage_key,
                                     dataset_keys=dataset_keys)
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


def _run_literal_value(*, ast, action_id, target_id, storage_key, dataset_keys, db_path) -> dict | None:
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
                                     storage_key=storage_key,
                                     dataset_keys=dataset_keys,
                                     literal=_ql_escape(str(lit)))
    if _expects_absence(ast):
        passed = len(rows) == 0
        return {
            "name":     "no_literal_value",
            "action":   action_id,
            "target":   target_id,
            "passed":   passed,
            "evidence": rows,
            "reason":   None if passed
                        else f"handler({action_id}) DOES write literal {lit!r} to "
                             f"{target_id}, but the constraint says it never should",
            "query":    query_text,
        }
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


def _run_source_set(*, ast, action_id, target_id, storage_key, dataset_keys, db_path) -> dict | None:
    """
    Rows 2 / 3 / D — verify the written value derives from EXACTLY the set
    of elements the value_expr names. Applies only when the value_expr
    reads at least one element. Self-skips otherwise.

    PASS iff the element sources reaching the write equal the expected set:
      - every expected element must flow in (the value uses what it claims)
      - no unexpected element may flow in (exclusivity / Row 3)
    """
    # Two ways the constraint can specify sources:
    #   1. Explicit set form  — w(target, sources={r(a), r(b)})
    #      Uses set-equality semantics. Empty set is meaningful
    #      ("no element sources flow in"), so we don't self-skip.
    #   2. Arithmetic value_expr — w(target, r(a) + r(b))
    #      Extracts every ReadExpr's element from the expression tree.
    #      Self-skips if no elements are referenced.
    explicit = _explicit_sources_for(ast, target_id)
    if explicit is not None:
        expected = set(explicit)
        explicit_form = True
    else:
        expected = set(_value_read_elements(ast, target_id))
        if not expected:
            return None
        explicit_form = False
    rows, query_text = _run_template("all_sources_to_sink.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id,
                                     storage_key=storage_key,
                                     dataset_keys=dataset_keys)
    # Storage reads return the raw key (e.g. "album"); translate back to
    # the storage-entry name (e.g. "albumStorage") so it compares against
    # the constraint's `r(albumStorage)` source spec.
    mapping = _safe_load_mapping()
    storage_entries = (mapping.get("storage") or {})
    key_to_entry = {
        (v or {}).get("key"): k
        for k, v in storage_entries.items()
        if isinstance((v or {}).get("key"), str)
    }
    actual = set()
    for r in rows:
        sid = r.get("source_id")
        if not sid:
            continue
        actual.add(key_to_entry.get(sid, sid))
    # Verdict semantics:
    #   Explicit set form `w(target, sources={...})` → SET EQUALITY
    #     (the user wrote an exact set; extras AND missing both fail).
    #   Arithmetic form `w(target, r(b) + r(c))`     → SUBSET
    #     (the listed reads must all flow in; extras allowed — matches
    #      how users naturally write "derives from b and c").
    missing = sorted(expected - actual)
    extra   = sorted(actual - expected)
    if explicit_form:
        passed = not missing and not extra
    else:
        passed = not missing
    parts = []
    if missing:
        parts.append(f"value should derive from {missing} but no flow was found")
    if extra and explicit_form:
        parts.append(f"value also derives from unexpected element(s) {extra}")
    if _expects_absence(ast):
        # The matching event ("write of t whose value derives from the
        # expected sources") must NOT occur. Inverted verdict: pass iff
        # the actual flow does NOT satisfy the expected source pattern
        # (some expected source missing, or — for explicit form — extras
        # break the equality). Covers "no write at all" too (actual=∅).
        return {
            "name":     "no_source_set",
            "action":   action_id,
            "target":   target_id,
            "passed":   not passed,
            "evidence": rows,
            "reason":   None if not passed
                        else f"value at write({target_id}) DOES derive from "
                             f"the expected source pattern in handler({action_id}), "
                             f"but the constraint says it never should",
            "query":    query_text,
        }
    return {
        "name":     "source_set",
        "action":   action_id,
        "target":   target_id,
        "passed":   passed,
        "evidence": rows,
        "reason":   None if passed else "; ".join(parts),
        "query":    query_text,
    }


def _run_api_result_taint(*, ast, action_id, target_id, storage_key, dataset_keys, db_path) -> dict | None:
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
                                     target_id=target_id,
                                     storage_key=storage_key,
                                     dataset_keys=dataset_keys)
    if _expects_absence(ast):
        passed = len(rows) == 0
        return {
            "name":     "no_api_result_taint",
            "action":   action_id,
            "target":   target_id,
            "passed":   passed,
            "evidence": rows,
            "reason":   None if passed
                        else f"an API response DOES flow into write({target_id}) "
                             f"in handler({action_id}), but the constraint says "
                             f"it never should",
            "query":    query_text,
        }
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


def _run_self_increment(*, ast, action_id, target_id, storage_key, dataset_keys, db_path) -> dict | None:
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
                                     target_id=target_id,
                                     storage_key=storage_key,
                                     dataset_keys=dataset_keys)
    if _expects_absence(ast):
        passed = len(rows) == 0
        return {
            "name":     "no_self_increment",
            "action":   action_id,
            "target":   target_id,
            "passed":   passed,
            "evidence": rows,
            "reason":   None if passed
                        else f"write({target_id}) in handler({action_id}) DOES "
                             f"add a literal constant to itself, but the "
                             f"constraint says it never should",
            "query":    query_text,
        }
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


def _run_all_paths_write(*, ast, action_id, target_id, storage_key, dataset_keys, db_path) -> dict | None:
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
                                     target_id=target_id,
                                     storage_key=storage_key,
                                     dataset_keys=dataset_keys)
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


def _run_no_other_handlers(*, ast, action_id, target_id, storage_key, dataset_keys, db_path) -> dict:
    """
    Run other_handlers_reach. PASS iff the result set is empty — i.e. no
    handler other than action_id's reaches a write on the target.
    """
    rows, query_text = _run_template("other_handlers_reach.ql",
                                     db_path=db_path,
                                     action_id=action_id,
                                     target_id=target_id,
                                     storage_key=storage_key,
                                     dataset_keys=dataset_keys)
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


def _run_guarded_write(*, ast, action_id, target_id, storage_key, dataset_keys, db_path) -> dict:
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
                                     storage_key=storage_key,
                                     dataset_keys=dataset_keys,
                                     guard_id=guard_id)
    if _expects_absence(ast):
        passed = len(rows) == 0
        return {
            "name":     "no_guarded_write",
            "action":   action_id,
            "target":   target_id,
            "passed":   passed,
            "evidence": rows,
            "reason":   None if passed
                        else f"write({target_id}) in handler({action_id}) IS gated by "
                             f"an if-statement reading {guard_id}, but the constraint "
                             f"says this guarded write never happens",
            "query":    query_text,
        }
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


def _explicit_sources_for(ast: dict, target_id: str) -> list[str] | None:
    """
    Element ids from the explicit `sources={...}` form on the target's
    WriteEvent, if present. Returns:
        - list of element names (possibly empty) when the WriteEvent
          uses the explicit set form
        - None when the WriteEvent has no explicit sources field (the
          caller falls back to value_expr extraction)

    The `api_result` sentinel is filtered out — element-source checks
    only verify DOM/storage flows.
    """
    for write in _all_writes_for(ast.get("event"), target_id):
        sources = write.get("sources")
        if sources is None:
            continue
        names: list[str] = []
        for item in sources:
            if not isinstance(item, dict):
                continue
            name = item.get("element")
            if isinstance(name, str) and name != "api_result":
                names.append(name)
        return names
    return None


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
        # `persist(target)` desugars to a save-side write — the analyzer
        # treats the persist target as a write target so action/target
        # extraction works uniformly.
        if node.get("type") == "PersistEvent" and isinstance(node.get("element"), str):
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
    """True if the AST references status(api), which Stage 1 does not
    support. CallEvent is intentionally NOT included — CallEvents at the
    top level are handled by _run_api_call_check, and CallEvents inside
    a CompoundEvent are handled by _evaluate_event_leaf."""
    if isinstance(ast, dict):
        if ast.get("type") == "StatusExpr":
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
