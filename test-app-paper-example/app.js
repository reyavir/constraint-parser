// Atlas Goods — order summary with promo code.

const promoInput     = document.getElementById("promo-input");
const promoStatus    = document.getElementById("promo-status");
const subtotalEl     = document.getElementById("subtotal");
const shippingEl     = document.getElementById("shipping");
const discountEl     = document.getElementById("discount");
const totalEl        = document.getElementById("total");
const checkoutTotal  = document.getElementById("checkout-total");

// Known promo codes → percent off the subtotal.
const PROMO_TABLE = {
  "WELCOME10":  0.10,
  "SAVE20":     0.20,
  "FRIEND15":   0.15,
};

function currentSubtotal() {
  return parseFloat(subtotalEl.textContent) || 0;
}
function currentShipping() {
  return parseFloat(shippingEl.textContent) || 0;
}

// Apply promo: look the entered code up, recompute the discount line
// and the grand total, mirror the total into the checkout button.
document.getElementById("apply-promo-btn").addEventListener("click", () => {
  const code = promoInput.value.trim().toUpperCase();
  const rate = PROMO_TABLE[code];
  if (!rate) {
    discountEl.textContent  = "0.00";
    totalEl.textContent     = (currentSubtotal() + currentShipping()).toFixed(2);
    checkoutTotal.textContent = totalEl.textContent;
    promoStatus.textContent = "Code not recognised.";
    promoStatus.className   = "promo-status";
    return;
  }
  const discount = currentSubtotal() * rate;
  discountEl.textContent    = discount.toFixed(2);
  totalEl.textContent       = (currentSubtotal() + currentShipping() - discount).toFixed(2);
  checkoutTotal.textContent = totalEl.textContent;
  promoStatus.textContent   = "Promo applied — " + code;
  promoStatus.className     = "promo-status success";
});

// Checkout: persist the order total the user is about to pay.
document.getElementById("checkout-btn").addEventListener("click", () => {
  localStorage.setItem("last-checkout-total", totalEl.textContent);
});
