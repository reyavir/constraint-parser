"""
Trace generation with Playwright.

Two entry points
----------------

``generate_traces(url, scenarios, …)``
    Hand-written scenarios — kept for backwards compatibility with the
    earlier ``trace_example.py`` demo.

``generate_traces_for_constraint(url, ast, mapping, …)``
    The one the verifier uses. Derives the required actions from a
    parsed constraint AST, optionally clicks ``random_suffix`` more
    elements (drawn from ``mapping.elements`` where ``kind == "action"``)
    for variation, and returns one *rollup* dict per trace.

Trace rollup shape
------------------

    {
        "id":                "trace_0000",
        "required_actions":  ["add-to-cart-btn"],
        "triggered":         ["add-to-cart-btn"],            # dedup'd, order preserved
        "triggered_seq":     ["add-to-cart-btn"],            # raw click order
        "written":           ["cart-count", "cart-total"],   # dedup'd, order preserved
        "written_values":    {"cart-count": "1",             # last value wins
                              "cart-total": "120.00"},
        "values_before":     {"cart-count": "0", ...},       # snapshot at __resetTrace
        "network":           [{"endpoint": "/api/cart",
                               "method":   "POST",
                               "status":   200,
                               "api_ref":  "/api/cart"}],
        "errors":            [],
        "skipped":           [],                             # required ids that weren't clickable
        "events":            [...]                           # full ordered event log
    }
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Callable

from playwright.sync_api import sync_playwright, Page, Route

from ..mapping.pipeline import load_mapping

_INSTRUMENTATION = Path(__file__).parent / "instrumentation.js"


# ─────────────────────────────────────────────────────────────────────────────
# Public — hand-written scenarios (legacy)
# ─────────────────────────────────────────────────────────────────────────────

def generate_traces(
    url: str,
    scenarios: list[tuple[str, Callable[[Page], None]]],
    *,
    n_per_scenario: int = 1,
    mock_responses: dict[str, dict] | None = None,
    headless: bool = True,
    wait_ms: int = 500,
) -> list[dict]:
    """
    Run each scenario under Playwright and return one *raw* payload per
    run (the result of ``window.__collectTrace()`` plus a scenario tag).
    Use this when the caller will aggregate the events themselves.
    """
    script = _load_script()

    raw: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            for scenario_name, scenario_fn in scenarios:
                for i in range(n_per_scenario):
                    payload = _run_one_trace(
                        browser,
                        url=url,
                        script=script,
                        trace_id=f"{scenario_name}_{i:04d}",
                        action_fn=scenario_fn,
                        mock_responses=mock_responses,
                        wait_ms=wait_ms,
                    )
                    payload["scenario"] = scenario_name
                    raw.append(payload)
        finally:
            browser.close()

    return raw


# ─────────────────────────────────────────────────────────────────────────────
# Public — constraint-driven (the one the verifier calls)
# ─────────────────────────────────────────────────────────────────────────────

def generate_traces_for_constraint(
    url: str,
    ast: dict,
    mapping: dict,
    *,
    n: int = 50,
    random_suffix: int = 3,
    mock_responses: dict[str, dict] | None = None,
    headless: bool = True,
    wait_ms: int = 500,
    click_settle_ms: int = 300,
    seed: int | None = None,
) -> list[dict]:
    """
    Generate *n* aggregated trace rollups for the given parsed constraint.

    For each trace:
      1. Reset instrumentation (snapshots ``values_before``).
      2. Click every element listed in ``ast["condition"]`` that is an
         Action (these are the *required* actions — they exist in the
         constraint's condition and must fire in every trace).
      3. Optionally click ``random_suffix`` additional elements drawn
         from ``mapping.elements`` where ``kind == "action"`` to add
         variation. Required elements are excluded from this pool so
         we don't double-click them.
      4. Wait ``wait_ms`` for async writes to settle, then collect
         the event log via ``__collectTrace()``.

    Each click is gated on ``is_visible() and is_enabled()``. If the
    element is not clickable the trace records it under ``skipped``
    so the verifier can see "user couldn't perform this action" rather
    than treating it as "user performed it and nothing happened".

    Returns
    -------
    List of rollup dicts (see module docstring for the shape).
    """
    required = _extract_required_actions(ast)

    action_pool = [
        eid for eid, info in (mapping.get("elements") or {}).items()
        if info.get("kind") == "action" and eid not in required
    ]
    rng = random.Random(seed)

    script = _load_script(mapping=mapping)

    rollups: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            for i in range(n):
                trace_id = f"trace_{i:04d}"
                extras = (rng.sample(action_pool, k=min(random_suffix, len(action_pool)))
                          if random_suffix > 0 and action_pool else [])

                action_plan = list(required) + extras

                def action_fn(page: Page, plan=action_plan, settle=click_settle_ms):
                    skipped: list[dict] = []
                    for elem_id in plan:
                        _try_click(page, elem_id, settle_ms=settle, skipped=skipped)
                    # Stash skipped on the page so __collectTrace can read it.
                    page.evaluate("(s) => { window.__skipped = s; }", skipped)

                payload = _run_one_trace(
                    browser,
                    url=url,
                    script=script,
                    trace_id=trace_id,
                    action_fn=action_fn,
                    mock_responses=mock_responses,
                    wait_ms=wait_ms,
                )

                # Pull whatever __skipped action_fn wrote.
                payload["skipped"] = payload.pop("_skipped", [])
                rollups.append(_aggregate(payload, required_actions=required))
        finally:
            browser.close()

    return rollups


# ─────────────────────────────────────────────────────────────────────────────
# Internal — Playwright session
# ─────────────────────────────────────────────────────────────────────────────

def _load_script(mapping: dict | None = None) -> str:
    """Read instrumentation.js and substitute the mapping placeholder."""
    if mapping is None:
        mapping = load_mapping()
    return _INSTRUMENTATION.read_text().replace("__MAPPING__", json.dumps(mapping))


def _run_one_trace(
    browser,
    *,
    url: str,
    script: str,
    trace_id: str,
    action_fn: Callable[[Page], None],
    mock_responses: dict[str, dict] | None,
    wait_ms: int,
) -> dict:
    """
    Open a fresh context, inject the instrumentation, navigate, reset the
    trace, run the action callable, settle, then call __collectTrace().
    Returns the dict that __collectTrace() produced (plus a stashed
    ``_skipped`` field if the action_fn wrote one to the page).
    """
    context = browser.new_context()
    page    = context.new_page()
    try:
        page.add_init_script(script)
        if mock_responses:
            _install_mocks(page, mock_responses)

        page.goto(url)
        page.wait_for_load_state("domcontentloaded")

        # Snapshot must happen *after* the page has rendered.
        page.evaluate("(id) => window.__resetTrace(id)", trace_id)

        action_fn(page)

        page.wait_for_timeout(wait_ms)

        payload = page.evaluate("() => window.__collectTrace()")
        payload["_skipped"] = page.evaluate("() => window.__skipped || []")
        return payload
    finally:
        context.close()


def _try_click(page: Page, elem_id: str, *, settle_ms: int, skipped: list[dict]) -> None:
    """
    Click ``#elem_id`` if it's visible and enabled, otherwise record a
    skip entry. Any unexpected exception from the click is captured into
    ``skipped`` rather than aborting the trace.
    """
    selector = f"#{elem_id}"
    loc = page.locator(selector)
    try:
        if loc.count() == 0:
            skipped.append({"id": elem_id, "reason": "not_in_dom"})
            return
        if not loc.first.is_visible():
            skipped.append({"id": elem_id, "reason": "not_visible"})
            return
        if not loc.first.is_enabled():
            skipped.append({"id": elem_id, "reason": "disabled"})
            return
        loc.first.click(timeout=1000)
        page.wait_for_timeout(settle_ms)
    except Exception as exc:
        skipped.append({"id": elem_id, "reason": "click_failed", "message": str(exc)})


def _install_mocks(page: Page, mock_responses: dict[str, dict]) -> None:
    """Register Playwright route handlers for each mocked endpoint."""
    for path, descriptor in mock_responses.items():
        status = descriptor.get("status", 200)
        if "body" in descriptor:
            content_type = "application/json"
            body         = json.dumps(descriptor["body"])
        else:
            content_type = "text/plain"
            body         = descriptor.get("text", "")

        def make_handler(s: int, ct: str, b: str):
            def handler(route: Route) -> None:
                route.fulfill(status=s, content_type=ct, body=b)
            return handler

        page.route(f"**{path}**", make_handler(status, content_type, body))


# ─────────────────────────────────────────────────────────────────────────────
# Internal — AST → required actions
# ─────────────────────────────────────────────────────────────────────────────

def _extract_required_actions(ast: dict) -> list[str]:
    """
    Walk ``ast["condition"]`` and collect element ids on every
    non-negated Action node. Negated actions (``¬A(x)``) are *not*
    required clicks — the constraint says these should NOT happen.
    """
    out: list[str] = []
    _walk_actions(ast.get("condition"), out)
    # Dedup but preserve first-seen order.
    seen, unique = set(), []
    for e in out:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def _walk_actions(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        if (node.get("type") == "Action"
                and isinstance(node.get("element"), str)
                and not node.get("negated")):
            out.append(node["element"])
        for v in node.values():
            _walk_actions(v, out)
    elif isinstance(node, list):
        for item in node:
            _walk_actions(item, out)


# ─────────────────────────────────────────────────────────────────────────────
# Internal — event log → rollup
# ─────────────────────────────────────────────────────────────────────────────

def _aggregate(payload: dict, *, required_actions: list[str]) -> dict:
    """Convert a raw ``__collectTrace()`` payload into the rollup shape."""
    events = payload.get("events", [])

    triggered_seq = [e["element"] for e in events if e.get("type") == "action"]
    triggered     = list(dict.fromkeys(triggered_seq))

    write_events  = [e for e in events if e.get("type") == "write"]
    written_seq   = [e["element"] for e in write_events]
    written       = list(dict.fromkeys(written_seq))

    written_values: dict[str, str] = {}
    for e in write_events:
        written_values[e["element"]] = e.get("value")

    # Pair api_call with the next api_response (FIFO). Calls without a
    # matching response keep status=None — happens on mocked routes that
    # don't trigger the response branch or on crashed fetches.
    network: list[dict] = []
    calls = [e for e in events if e.get("type") == "api_call"]
    resps = [e for e in events if e.get("type") == "api_response"]
    for i, c in enumerate(calls):
        r = resps[i] if i < len(resps) else None
        network.append({
            "endpoint": c.get("endpoint"),
            "method":   c.get("method"),
            "api_ref":  c.get("api_ref"),
            "status":   (r or {}).get("status"),
            "ok":       (r or {}).get("ok"),
        })

    return {
        "id":               payload.get("id"),
        "required_actions": required_actions,
        "triggered":        triggered,
        "triggered_seq":    triggered_seq,
        "written":          written,
        "written_values":   written_values,
        "values_before":    payload.get("values_before", {}),
        "network":          network,
        "errors":           payload.get("errors", []),
        "skipped":          payload.get("skipped", []),
        "events":           events,
    }
