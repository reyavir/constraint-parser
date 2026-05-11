"""
Trace generation with Playwright.

Trace format
------------
A trace is a dict representing one run of one scenario:

    {
        "scenario": "click_add_to_cart",
        "events": [
            {
                "seq":        0,
                "type":       "action",
                "element":    "addToCartBtn",
                "event_name": "click",
                "timestamp":  1713456789012
            },
            {
                "seq":        1,
                "type":       "api_call",
                "api_ref":    "cartApi",
                "endpoint":   "/api/cart",
                "method":     "POST",
                "timestamp":  1713456789034
            },
            {
                "seq":        2,
                "type":       "write",
                "element":    "cartCountDisplay",
                "property":   "textContent",
                "value":      "1",
                "timestamp":  1713456789056
            },
        ]
    }

generate_traces() returns a list of such dicts — one per scenario run.
Events within each trace are ordered by seq (ascending).

Usage
-----
    from src.tracer.runner import generate_traces
    from playwright.sync_api import Page

    def click_add_to_cart(page: Page) -> None:
        page.click("#add-to-cart-btn")
        page.wait_for_timeout(500)

    traces = generate_traces(
        url="http://localhost:8080",
        scenarios=[("click_add_to_cart", click_add_to_cart)],
        n_per_scenario=20,
        mock_responses={
            "/api/cart": {
                "status": 200,
                "body": {"items": [{"name": "Keyboard", "qty": 1, "price": "120.00"}],
                         "totalItems": 1, "totalPrice": 120.0},
            },
        },
    )
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from playwright.sync_api import sync_playwright, Page, Route

from ..mapping.pipeline import load_mapping

_INSTRUMENTATION = Path(__file__).parent / "instrumentation.js"


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
    Run each scenario under Playwright and return the collected traces.

    Parameters
    ----------
    url:
        URL of the app (e.g. ``"http://localhost:8080"``).
    scenarios:
        List of ``(name, fn)`` pairs.  ``fn(page)`` performs the
        user interactions for one scenario run.
    n_per_scenario:
        How many times to repeat each scenario.  Increase this to get
        enough samples for probabilistic verification.
    mock_responses:
        Optional dict mapping URL path → response descriptor so fetch
        calls don't just fail.  Each descriptor may have:
        ``status`` (int, default 200), ``body`` (dict → JSON), ``text``
        (str).  Example::

            {"/api/cart": {"status": 200, "body": {"totalItems": 1}}}

    headless:
        Run browser in headless mode.
    wait_ms:
        Milliseconds to wait after each scenario for async effects to
        settle before collecting ``window.__traces``.

    Returns
    -------
    List of trace dicts — one per scenario run.
    """
    mapping = load_mapping()
    script  = _INSTRUMENTATION.read_text().replace(
        "__MAPPING__", json.dumps(mapping)
    )

    traces: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)

        for scenario_name, scenario_fn in scenarios:
            for _ in range(n_per_scenario):
                context = browser.new_context()
                page    = context.new_page()

                # Inject instrumentation before any page JS runs
                page.add_init_script(script)

                # Mock API responses so fetch calls return real data
                if mock_responses:
                    _install_mocks(page, mock_responses)

                page.goto(url)
                page.wait_for_load_state("domcontentloaded")

                scenario_fn(page)

                page.wait_for_timeout(wait_ms)

                events: list[dict] = page.evaluate("() => window.__traces || []")
                events.sort(key=lambda e: e.get("seq", 0))

                traces.append({"scenario": scenario_name, "events": events})

                context.close()

        browser.close()

    return traces


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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

        # Capture loop vars in a closure
        def make_handler(s: int, ct: str, b: str):
            def handler(route: Route) -> None:
                route.fulfill(status=s, content_type=ct, body=b)
            return handler

        page.route(f"**{path}**", make_handler(status, content_type, body))
