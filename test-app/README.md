# Test App — Add to Cart

Simple vanilla JS shop used to test the CodeQL element mapping pipeline.

## What's in it

| Element            | ID                  | Kind      | Expected mapping name |
|--------------------|---------------------|-----------|-----------------------|
| Add to Cart button | `add-to-cart-btn`   | action    | `addToCartBtn`        |
| Checkout button    | `checkout-btn`      | action    | `checkoutBtn`         |
| Search button      | `search-btn`        | action    | `searchBtn`           |
| Qty input          | `qty-input`         | action    | `qtyInput`            |
| Search input       | `search-input`      | action    | `searchInput`         |
| Cart count display | `cart-count`        | component | `cartCountDisplay`    |
| Cart total display | `cart-total`        | component | `cartTotalDisplay`    |
| Cart item list     | `cart-list`         | component | `cartList`            |
| Error display      | `error-display`     | component | `errorDisplay`        |
| Search results     | `search-results`    | component | `searchResults`       |
| Cart API           | `/api/cart`         | api       | `cartApi`             |
| Checkout API       | `/api/checkout`     | api       | `checkoutApi`         |
| Search API         | `/api/search`       | api       | `searchApi`           |
| Error handler      | cart.js:31          | error     | —                     |
| Error handler      | cart.js:54          | error     | —                     |
| Error handler      | search.js:18        | error     | —                     |

## Running CodeQL

```bash
# 1. Build the database (run from the repo root)
codeql database create ./codeql-db \
  --language=javascript \
  --source-root=./test-app \
  --overwrite

# 2. Run the mapping pipeline
python -c "
from src.mapping import generate_element_mapping
generate_element_mapping('./codeql-db')
"

# 3. Review the output
cat element_mapping.json
```

## What to verify

After running, `element_mapping.json` should contain all elements from the table above.
Check that:
- All 5 action elements are present
- All 5 display elements have a `read_property` set correctly
- All 3 API endpoints are captured
- All 3 catch blocks appear in `error_handlers`
