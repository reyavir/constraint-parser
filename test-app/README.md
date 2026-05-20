# Test App — Shop demo

A small vanilla-JS shop used as a fixture for the constraint-verification
system. Frontend is plain HTML/JS in this directory; the matching backend
lives in `app/demo_backend.py` and is auto-registered when you run the
main Flask app.

## Running

One command from the repo root:

```bash
python run.py
```

Then open `http://localhost:5050/`. The Dynamic Analysis tab pre-fills
its URL to `/run/`, which serves this app from the same Flask process.
No second terminal, no separate backend to start.

## Endpoints (served from the main Flask app)

| Route             | Method | What it does                          |
|-------------------|--------|---------------------------------------|
| `/run/`           | GET    | The shop page (this directory's index.html) |
| `/run/<file>`     | GET    | Other static files (cart.js, search.js, style.css) |
| `/api/cart`       | POST   | Add item to cart, returns cart state  |
| `/api/checkout`   | POST   | Place order, clears cart              |
| `/api/search`     | GET    | Search the product catalog            |
| `/api/analytics`  | POST   | Event sink (fire-and-forget)          |
| `/api/health`     | GET    | Status check                          |

Cart state is per-session, keyed by a `cv_session` cookie the server sets
on first request. Fresh Playwright contexts get empty carts automatically.

## Elements

API-backed interactions (`cart.js`, `search.js`):

| Element            | ID                  | Kind      |
|--------------------|---------------------|-----------|
| Add to Cart button | `add-to-cart-btn`   | action    |
| Checkout button    | `checkout-btn`      | action    |
| Search button      | `search-btn`        | action    |
| Search input       | `search-input`      | action    |
| Cart count         | `cart-count`        | component |
| Cart total         | `cart-total`        | component |
| Cart item list     | `cart-list`         | component |
| Error display      | `error-display`     | component |
| Search results     | `search-results`    | component |

Pure-frontend interactions (`local.js`, no API):

| Element              | ID                | Kind      |
|----------------------|-------------------|-----------|
| Qty + button         | `qty-plus-btn`    | action    |
| Qty − button         | `qty-minus-btn`   | action    |
| Qty input            | `qty-input`       | action    |
| Favorite button      | `favorite-btn`    | action    |
| Favorite counter     | `favorite-count`  | component |
| Favorite list        | `favorite-list`   | component |

## Example constraints

### API-backed
```
P(w(cart-count) | A(add-to-cart-btn)) = 1   # PASSES — cart updates on click
P(w(cart-list)  | A(add-to-cart-btn)) = 1   # PASSES — item list re-renders
P(w(cart-count) | A(search-btn))      = 1   # FAILS  — search doesn't touch cart
```

### Pure-frontend — IncrementExpr
```
P(w(qty-input, r(qty-input) + 1) | A(qty-plus-btn)) = 1   # PASSES — +1 each click
P(w(qty-input) | A(qty-plus-btn))                   = 1   # PASSES — write happens
P(w(qty-input) | A(qty-minus-btn))                  = 0   # PASSES — clamped at 1, no write
```

The first row is the IncrementExpr form (`r(x) + 1`). The third row uses
the **counterfactual** form: when qty is already at the minimum, clicking
`−` is a no-op, so the *expected* probability of a write is 0.

### Pure-frontend — compound events
```
P(w(favorite-count) | A(favorite-btn))                          = 1
P(w(favorite-count) AND w(favorite-list) | A(favorite-btn))     = 1
```

The compound form (`w(a) AND w(b)`) requires both writes to fire on the
same trace. The favorite handler updates both the counter and the list
on every click, so both PASS.

## Constraints with caveats

`search-btn`'s handler bails out if `#search-input` is empty
(`if (!query) return;`). The current tracer only clicks elements — it
doesn't yet type into inputs — so constraints like
`P(w(search-results) | A(search-btn)) = 1` come back FAILED because of
the test setup, not because of an app bug. Type-then-click action
support is open work.
