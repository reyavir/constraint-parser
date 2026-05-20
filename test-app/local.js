// Local-only interactions for the shop demo.
//
// Nothing in this file calls fetch / hits the backend. These handlers
// exist to give the constraint-verification system a few pure-frontend
// behaviors to verify (increment / decrement / compound writes) alongside
// the API-backed ones in cart.js + search.js.

// ── Quantity stepper ──────────────────────────────────────────────────────

const qtyPlusBtn  = document.getElementById("qty-plus-btn");
const qtyMinusBtn = document.getElementById("qty-minus-btn");
const qtyField    = document.getElementById("qty-input");

const QTY_MIN = 1;
const QTY_MAX = 99;

qtyPlusBtn.addEventListener("click", function () {
  const current = parseInt(qtyField.value, 10) || QTY_MIN;
  if (current >= QTY_MAX) return;           // clamp at max — silent no-op
  qtyField.value = current + 1;
});

qtyMinusBtn.addEventListener("click", function () {
  const current = parseInt(qtyField.value, 10) || QTY_MIN;
  if (current <= QTY_MIN) return;           // clamp at min — silent no-op
  qtyField.value = current - 1;
});

// ── Favorite toggle (with counter + list) ────────────────────────────────

const favoriteBtn   = document.getElementById("favorite-btn");
const favoriteCount = document.getElementById("favorite-count");
const favoriteList  = document.getElementById("favorite-list");
const productName   = document.getElementById("product-name");

let favorites = [];

favoriteBtn.addEventListener("click", function () {
  const name = productName.textContent.trim();
  const idx  = favorites.indexOf(name);

  if (idx === -1) {
    favorites.push(name);
    favoriteBtn.textContent = "♥ Favorited";
  } else {
    favorites.splice(idx, 1);
    favoriteBtn.textContent = "♡ Favorite";
  }

  // Two writes per click — counter and list — so this also demonstrates
  // compound-event constraints (w(favorite-count) AND w(favorite-list)).
  favoriteCount.textContent = favorites.length;
  favoriteList.innerHTML    = favorites.length
    ? favorites.map(n => `<div class="favorite-item">${n}</div>`).join("")
    : "";
});
