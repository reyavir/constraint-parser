// Cart state
let cartItems = [];

const cartCount   = document.getElementById("cart-count");
const cartTotal   = document.getElementById("cart-total");
const cartList    = document.getElementById("cart-list");
const errorDisplay = document.getElementById("error-display");
const addBtn      = document.getElementById("add-to-cart-btn");
const checkoutBtn = document.getElementById("checkout-btn");
const qtyInput    = document.getElementById("qty-input");

// ── Add to cart ────────────────────────────────────────────────────────────

addBtn.addEventListener("click", async function () {
  const qty = parseInt(qtyInput.value, 10);

  try {
    const response = await fetch("/api/cart", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ productId: "product-1", qty }),
    });

    if (!response.ok) {
      throw new Error("Server error: " + response.status);
    }

    const data = await response.json();

    cartItems = data.items;

    // Update displays
    cartCount.textContent  = data.totalItems;
    cartTotal.textContent  = data.totalPrice.toFixed(2);
    cartList.innerHTML     = renderCartItems(data.items);
    errorDisplay.textContent = "";

  } catch (err) {
    errorDisplay.textContent = "Failed to add item: " + err.message;
  }
});

// ── Checkout ───────────────────────────────────────────────────────────────

checkoutBtn.addEventListener("click", async function () {
  try {
    const response = await fetch("/api/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: cartItems }),
    });

    if (!response.ok) {
      throw new Error("Checkout failed: " + response.status);
    }

    const data = await response.json();

    cartItems              = [];
    cartCount.textContent  = 0;
    cartTotal.textContent  = "0.00";
    cartList.innerHTML     = "";
    errorDisplay.textContent = "Order placed! Ref: " + data.orderId;

  } catch (err) {
    errorDisplay.textContent = "Checkout error: " + err.message;
  }
});

// ── Helpers ────────────────────────────────────────────────────────────────

function renderCartItems(items) {
  if (!items.length) return "<p>Empty</p>";
  return items
    .map(item => `<div class="cart-item">${item.name} × ${item.qty} — $${item.price}</div>`)
    .join("");
}
