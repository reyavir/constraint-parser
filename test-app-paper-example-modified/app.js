// Atlas Goods — order summary with promo code.

const promoInput     = document.getElementById("promo-input");
const promoStatus    = document.getElementById("promo-status");
const subtotalEl     = document.getElementById("subtotal");
const shippingEl     = document.getElementById("shipping");
const discountEl     = document.getElementById("discount");
const totalEl        = document.getElementById("total");
const checkoutTotal  = document.getElementById("checkout-total");

// Known promo codes — wired up in a future revision.
const PROMO_TABLE = {
  "WELCOME10":  0.10,
  "SAVE20":     0.20,
  "FRIEND15":   0.15,
};

// Apply promo: confirm to the user that their code went through.
document.getElementById("apply-promo-btn").addEventListener("click", () => {
  const code = promoInput.value.trim().toUpperCase();
  promoStatus.textContent = "Promo applied — " + code;
  promoStatus.className   = "promo-status success";
});

// Checkout: persist the order total the user is about to pay.
document.getElementById("checkout-btn").addEventListener("click", () => {
  localStorage.setItem("last-checkout-total", totalEl.textContent);
});
