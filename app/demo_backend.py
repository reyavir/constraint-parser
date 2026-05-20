"""
Demo backend for the bundled test-app.

These routes piggy-back on the main Flask app so a single `python run.py`
gives the user a complete, runnable demo:

    /run/                  → test-app/index.html (no overlay)
    /run/<file>            → other test-app static files
    POST /api/cart         → add item, returns cart state
    POST /api/checkout     → place order, clears cart
    GET  /api/search       → search the hardcoded catalog
    POST /api/analytics    → fire-and-forget event sink
    GET  /api/health       → status check

Cart state is per-session, keyed by a `cv_session` cookie the server sets
on first request. Fresh browser / Playwright contexts get empty carts
automatically.

When the user runs their *own* app instead of the bundled demo, they
ignore these routes entirely — they just put their app's URL into the
Dynamic Analysis field.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory


TEST_APP_DIR = (Path(__file__).parent.parent / "test-app").resolve()

bp = Blueprint("demo_backend", __name__)


# ─────────────────────────────────────────────────────────────────────────
# Hardcoded product catalog
# ─────────────────────────────────────────────────────────────────────────

PRODUCTS = [
    {"id": "product-1", "name": "Mechanical Keyboard", "price": 120.00,
     "keywords": ["keyboard", "mechanical"]},
    {"id": "product-2", "name": "Wireless Mouse",      "price":  35.00,
     "keywords": ["mouse", "wireless"]},
    {"id": "product-3", "name": "USB-C Hub",           "price":  45.00,
     "keywords": ["hub", "usb", "dongle"]},
    {"id": "product-4", "name": "Standing Desk Mat",   "price":  60.00,
     "keywords": ["mat", "desk", "standing"]},
    {"id": "product-5", "name": "Webcam HD",           "price":  80.00,
     "keywords": ["webcam", "camera", "video"]},
]


# ─────────────────────────────────────────────────────────────────────────
# In-memory state (process-local)
# ─────────────────────────────────────────────────────────────────────────

_CARTS:  dict[str, list[dict]] = {}     # session_id → cart items
_ORDERS: dict[str, int]        = {"n": 0}


def _session_id() -> str:
    return request.cookies.get("cv_session") or uuid.uuid4().hex


def _with_cookie(resp, sid: str):
    resp.set_cookie("cv_session", sid, samesite="Lax")
    return resp


def _cart_payload(cart: list[dict]) -> dict:
    total_items = sum(item["qty"] for item in cart)
    total_price = round(sum(item["qty"] * item["price"] for item in cart), 2)
    return {"items": cart, "totalItems": total_items, "totalPrice": total_price}


# ─────────────────────────────────────────────────────────────────────────
# Static file serving for the demo app
# ─────────────────────────────────────────────────────────────────────────

@bp.get("/run/")
def run_index():
    return send_from_directory(TEST_APP_DIR, "index.html")


@bp.get("/run/<path:filename>")
def run_static(filename: str):
    return send_from_directory(TEST_APP_DIR, filename)


# ─────────────────────────────────────────────────────────────────────────
# JSON API
# ─────────────────────────────────────────────────────────────────────────

@bp.post("/api/cart")
def api_cart():
    sid  = _session_id()
    body = request.get_json(silent=True) or {}
    product_id = body.get("productId")
    qty        = body.get("qty")

    if not isinstance(product_id, str) or not product_id:
        return jsonify({"error": "missing productId"}), 400
    if not isinstance(qty, int) or qty < 1:
        return jsonify({"error": "qty must be a positive integer"}), 400

    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if product is None:
        return jsonify({"error": f"unknown product: {product_id}"}), 404

    cart = _CARTS.setdefault(sid, [])
    existing = next((c for c in cart if c["productId"] == product_id), None)
    if existing:
        existing["qty"] += qty
    else:
        cart.append({
            "productId": product_id,
            "name":      product["name"],
            "qty":       qty,
            "price":     product["price"],
        })
    return _with_cookie(jsonify(_cart_payload(cart)), sid)


@bp.post("/api/checkout")
def api_checkout():
    sid  = _session_id()
    cart = _CARTS.get(sid, [])
    if not cart:
        return jsonify({"error": "cart is empty"}), 400

    _ORDERS["n"] += 1
    order_id = f"ORD-{_ORDERS['n']:04d}"
    _CARTS[sid] = []
    return _with_cookie(jsonify({"orderId": order_id}), sid)


@bp.get("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"results": []})
    matches = [
        {"name": p["name"], "price": f"{p['price']:.2f}"}
        for p in PRODUCTS
        if q in p["name"].lower() or any(q in kw for kw in p["keywords"])
    ]
    return jsonify({"results": matches})


@bp.post("/api/analytics")
def api_analytics():
    return jsonify({"ok": True})


@bp.get("/api/health")
def api_health():
    return jsonify({
        "ok": True,
        "products":      len(PRODUCTS),
        "active_carts":  len(_CARTS),
        "orders_placed": _ORDERS["n"],
    })
