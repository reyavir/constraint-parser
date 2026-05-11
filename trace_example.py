"""
Example: generate traces for the test-app and print them.

Start the test app first:
    cd test-app && python -m http.server 8080

Then run:
    python trace_example.py
"""

import json
from playwright.sync_api import Page
from src.tracer import generate_traces

# ── Scenarios ──────────────────────────────────────────────────────────────
# Each scenario is a (name, fn) pair. fn(page) drives one user interaction.

def click_add_to_cart(page: Page) -> None:
    page.click("#add-to-cart-btn")

def click_checkout(page: Page) -> None:
    page.click("#add-to-cart-btn")
    page.wait_for_timeout(300)
    page.click("#checkout-btn")

def search_something(page: Page) -> None:
    page.fill("#search-input", "keyboard")
    page.click("#search-btn")

# ── Mock API responses (so fetch calls return real data) ───────────────────

MOCKS = {
    "/api/cart": {
        "status": 200,
        "body": {
            "items":       [{"name": "Keyboard", "qty": 1, "price": "120.00"}],
            "totalItems":  1,
            "totalPrice":  120.0,
        },
    },
    "/api/checkout": {
        "status": 200,
        "body": {"orderId": "ORD-001"},
    },
    "/api/search": {
        "status": 200,
        "body": {
            "results": [{"name": "Mechanical Keyboard", "price": "120.00"}],
        },
    },
}

# ── Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    traces = generate_traces(
        url="http://localhost:8080",
        scenarios=[
            ("click_add_to_cart", click_add_to_cart),
            ("click_checkout",    click_checkout),
            ("search_something",  search_something),
        ],
        n_per_scenario=3,
        mock_responses=MOCKS,
        headless=True,
    )

    print(f"Collected {len(traces)} traces\n")
    for trace in traces:
        print(f"── {trace['scenario']} ({len(trace['events'])} events)")
        for ev in trace["events"]:
            print(f"   [{ev['seq']}] {ev['type']:10} {ev.get('element') or ev.get('api_ref', ''):<20} {ev.get('event_name') or ev.get('property') or ev.get('method', '')}")
        print()
