// Stayz — minimal listings demo.
//
// Every interactive element has a static id. Every handler is bound via
// `document.getElementById('X').addEventListener(...)`. No body
// delegation, no `.onclick = fn`, no dynamic id creation. Designed so
// the Stage-1 constraint verifier can reason about each action cleanly.

const LISTINGS = {
  "1": { name: "Beach bungalow", price: 120 },
  "2": { name: "City loft",      price: 210 },
  "3": { name: "Forest cabin",   price: 310 },
};

let favorites = new Set();

const favCount         = document.getElementById("fav-count");
const visibleCount     = document.getElementById("visible-count");
const lastBookingName  = document.getElementById("last-booking-name");
const lastBookingTotal = document.getElementById("last-booking-total");
const lastBookingGuestsSpan = document.getElementById("last-booking-guests");
const guestsInput      = document.getElementById("guests-input");
const searchInput      = document.getElementById("search-input");

// ── Favorite toggles ──────────────────────────────────────────────────
// Skip persisting an empty array — no point writing an empty list
// when the user has no favorites left.
function toggleFavorite(listingId) {
  if (favorites.has(listingId)) favorites.delete(listingId);
  else                          favorites.add(listingId);
  favCount.textContent = favorites.size;
  if (favorites.size > 0) {
    localStorage.setItem("favorites", JSON.stringify([...favorites]));
  }
}

document.getElementById("fav-1").addEventListener("click", () => { toggleFavorite("1"); });
document.getElementById("fav-2").addEventListener("click", () => { toggleFavorite("2"); });
function persistFavorites() {
  localStorage.setItem("favorites", JSON.stringify([...favorites]));
}

document.getElementById("fav-3").addEventListener("click", () => {
  const wasFavorite = favorites.has("3");
  if (wasFavorite) {
    favorites.delete("3");
    favCount.textContent = String(favorites.size);
    persistFavorites();
  } else {
    favorites.add("3");
    favCount.textContent = String(favorites.size);
  }
});

// ── Booking buttons ───────────────────────────────────────────────────
function bookListing(listingId) {
  const listing = LISTINGS[listingId];
  const guests  = parseInt(guestsInput.value, 10) || 1;
  const total   = listing.price * guests;
  lastBookingName.textContent       = listing.name;
  lastBookingGuestsSpan.textContent = String(guests);
  displayBookingTotal(total, guests);
  localStorage.setItem("last-booking", JSON.stringify({
    name:   listing.name,
    guests: guests,
    total:  total,
  }));
}

function displayBookingTotal(total, guests) {
  if (guests <= 4) {
    lastBookingTotal.textContent = String(total);
  }
}

document.getElementById("book-1").addEventListener("click", () => { bookListing("1"); });
document.getElementById("book-2").addEventListener("click", () => { bookListing("2"); });
document.getElementById("book-3").addEventListener("click", () => { bookListing("3"); });

// ── Price filters ─────────────────────────────────────────────────────
// Each filter button recomputes how many listings remain visible.
// Updates visible-count on every code path (no early returns).
function applyPriceFilter(predicate) {
  let n = 0;
  for (const id of Object.keys(LISTINGS)) {
    const card = document.getElementById("listing-" + id);
    const show = predicate(LISTINGS[id].price);
    card.style.display = show ? "" : "none";
    if (show) n += 1;
  }
  visibleCount.textContent = String(n);
}

// "Any" trivially shows everything, so we skip the filter loop and
// just unhide every card directly.
document.getElementById("filter-any").addEventListener("click", () => {
  for (const id of Object.keys(LISTINGS)) {
    document.getElementById("listing-" + id).style.display = "";
  }
});
document.getElementById("filter-low").addEventListener("click", () => {
  applyPriceFilter(price => price < 150);
});
document.getElementById("filter-mid").addEventListener("click", () => {
  applyPriceFilter(price => price >= 150 && price <= 250);
});
document.getElementById("filter-high").addEventListener("click", () => {
  applyPriceFilter(price => price > 250);
});

// ── Search button ─────────────────────────────────────────────────────
// Filters by listing name substring. Also surfaces how many of the
// matching results are favorited, so the user can spot saved listings
// inside the filtered set at a glance.
document.getElementById("search-btn").addEventListener("click", () => {
  const term = searchInput.value.trim().toLowerCase();
  let n = 0;
  let favMatches = 0;
  for (const id of Object.keys(LISTINGS)) {
    const card = document.getElementById("listing-" + id);
    const show = !term || LISTINGS[id].name.toLowerCase().includes(term);
    card.style.display = show ? "" : "none";
    if (show) {
      n += 1;
      if (favorites.has(id)) favMatches += 1;
    }
  }
  visibleCount.textContent = String(n);
  favCount.textContent = String(favMatches);
});

// ── Reset booking ─────────────────────────────────────────────────────
// Clears the visible last-booking summary and wipes any stale
// persisted favorites so the session starts clean.
document.getElementById("reset-booking-btn").addEventListener("click", () => {
  lastBookingName.textContent       = "—";
  lastBookingGuestsSpan.textContent = "—";
  lastBookingTotal.textContent      = "0";
  localStorage.setItem("favorites", "[]");
});

// ── Guest stepper (Row A — self-increment) ────────────────────────────
// Both write guests-input with `r(guests-input) + 1` / `- 1`.
// Constraint  P(w(guests-input, r(guests-input) + 1) | A(guest-plus-btn)) = 1
// should PASS self_increment + source_set (guests-input among sources).
document.getElementById("guest-plus-btn").addEventListener("click", () => {
  guestsInput.value = (parseInt(guestsInput.value, 10) || 0) + 1;
});
document.getElementById("guest-minus-btn").addEventListener("click", () => {
  guestsInput.value = (parseInt(guestsInput.value, 10) || 0) - 1;
});

// ── Fees calculator (Row D — multi-source sum) ────────────────────────
// total-with-fees = base-price-input + cleaning-input + service-input.
// Constraint
//   P(w(total-with-fees, r(base-price-input) + r(cleaning-input) + r(service-input))
//      | A(compute-fees-btn)) = 1
// should PASS source_set (exact-set match across all three sources).
const basePriceInput = document.getElementById("base-price-input");
const cleaningInput  = document.getElementById("cleaning-input");
const serviceInput   = document.getElementById("service-input");
const totalWithFees  = document.getElementById("total-with-fees");

document.getElementById("compute-fees-btn").addEventListener("click", () => {
  const total = parseFloat(basePriceInput.value) +
                parseFloat(cleaningInput.value) +
                parseFloat(serviceInput.value);
  totalWithFees.textContent = String(total);
  // Persist the latest computed total so the next page load can show it.
  localStorage.setItem("last-booking", JSON.stringify({ total: total }));
});

// ── Review submission (Row 5 — guarded write) ─────────────────────────
// review-thanks is written only when rating-input is positive.
// Constraint
//   P(w(review-thanks) | A(submit-review-btn), r(rating-input) > 0) = 1
// should PASS guarded_write (structural: the write sits inside an `if`
// whose condition reads rating-input).
const ratingInput  = document.getElementById("rating-input");
const reviewThanks = document.getElementById("review-thanks");

document.getElementById("submit-review-btn").addEventListener("click", () => {
  if (parseInt(ratingInput.value, 10) > 0) {
    reviewThanks.textContent = "Thanks for your review!";
  }
});
