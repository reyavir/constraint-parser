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

// ── Delegating handler (fixture for inter-procedural all_paths_write) ────
// Demonstrates the inter-procedural behaviour: this handler doesn't write
// the status element directly — it delegates to setStatus(). The naive
// intra-procedural check would say "no write to status-display in the
// handler" and FAIL P=1; the inter-procedural check correctly traces into
// setStatus, sees it unconditionally writes status-display on every path,
// and PASSes.

const greetBtn      = document.getElementById("greet-btn");
const statusDisplay = document.getElementById("status-display");

function setStatus(message) {
  statusDisplay.textContent = message;
}

greetBtn.addEventListener("click", function () {
  setStatus("hello");
});

// ── Row 2 fixture: mirror input value into a display ────────────────────
// Every "input" event reads mirrorInput.value and writes it to
// mirrorDisplay.textContent. No branches, no early returns — the only
// path through the handler dominates the write. Constraint
//   P(w(mirror-display, r(mirror-input)) | A(mirror-input)) = 1
// should PASS every static check (path_exists, source_set,
// all_paths_write); self_increment self-skips.

const mirrorInput   = document.getElementById("mirror-input");
const mirrorDisplay = document.getElementById("mirror-display");

mirrorInput.addEventListener("input", function () {
  mirrorDisplay.textContent = mirrorInput.value;
});

// ── Row 5 fixture: guarded write ────────────────────────────────────────
// The greeting is written only when the name field reads a specific value.
// Constraint
//   P(w(greeting-display) | A(submit-btn) AND r(name-input) = "alice") = 1
// should PASS guarded_write (the write to greeting-display is nested in an
// if-statement whose condition reads name-input). all_paths_write
// self-skips because the condition has a guard.

const submitBtn        = document.getElementById("submit-btn");
const nameInput        = document.getElementById("name-input");
const greetingDisplay  = document.getElementById("greeting-display");

submitBtn.addEventListener("click", function () {
  if (nameInput.value === "alice") {
    greetingDisplay.textContent = "Hi Alice!";
  }
});

// ── Order total fixture ────────────────────────────────────────────────
// computeBtn: order-total derives from EXACTLY three element sources
//   (order-subtotal + tax-input + tip-input). Demonstrates the
//   multi-source sum case (Row D-style).
//     P(w(order-total, r(order-subtotal) + r(tax-input) + r(tip-input))
//        | A(compute-btn)) = 1
//   should PASS path_exists, source_set (exact-set match), all_paths_write.
//
// resetTotalBtn: order-total set to the literal "0.00", unconditionally.
//   Demonstrates Row C (constant k).
//     P(w(order-total, "0.00") | A(reset-total-btn)) = 1
//   should PASS path_exists, literal_value, all_paths_write.

const orderSubtotal = document.getElementById("order-subtotal");
const taxInput      = document.getElementById("tax-input");
const tipInput      = document.getElementById("tip-input");
const computeBtn    = document.getElementById("compute-btn");
const orderTotal    = document.getElementById("order-total");
const resetTotalBtn = document.getElementById("reset-total-btn");

computeBtn.addEventListener("click", function () {
  orderTotal.textContent =
    parseFloat(orderSubtotal.textContent) +
    parseFloat(taxInput.value) +
    parseFloat(tipInput.value);
});

resetTotalBtn.addEventListener("click", function () {
  orderTotal.textContent = "0.00";
});

// ── Running-tally fixture (target reads itself + 2 other components) ──
// Each click adds a (charge + fee) line to the running tally.
// Constraint
//   P(w(tally-display, r(tally-display) + r(charge-input) + r(fee-input))
//      | A(add-tally-btn)) = 1
// should PASS path_exists, source_set (exact-set match including the
// target itself as a source), all_paths_write.

const tallyDisplay = document.getElementById("tally-display");
const chargeInput  = document.getElementById("charge-input");
const feeInput     = document.getElementById("fee-input");
const addTallyBtn  = document.getElementById("add-tally-btn");

addTallyBtn.addEventListener("click", function () {
  tallyDisplay.textContent =
    parseFloat(tallyDisplay.textContent) +
    parseFloat(chargeInput.value) +
    parseFloat(feeInput.value);
});
