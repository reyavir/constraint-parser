// Inventory fixture: items live in localStorage["inventory"] and the
// rendered list is sourced from there. Demonstrates storage-as-DB:
//
//   - On page load, if "inventory" is missing, seed it.
//   - Reset button re-seeds and re-renders.
//
// Constraints we can verify against this:
//   P(w(inventoryStorage) | A(reset-inventory-btn)) = 1   should PASS
//   P(w(inventory-status, r(inventoryStorage)) | A(reset-inventory-btn)) = 1
//                                                         (status text mirrors count)

const INVENTORY_KEY = "inventory";

const DEFAULT_INVENTORY = [
  { id: "keyboard",   name: "Mechanical Keyboard", price: 120.00 },
  { id: "headphones", name: "Over-ear Headphones", price: 80.00 },
  { id: "charger",    name: "USB-C Charger",       price: 25.00 },
];

const inventoryList   = document.getElementById("inventory-list");
const resetInvBtn     = document.getElementById("reset-inventory-btn");
const inventoryStatus = document.getElementById("inventory-status");

function seedInventory() {
  const payload = JSON.stringify(DEFAULT_INVENTORY);
  localStorage.setItem("inventory", payload);
}

function loadInventory() {
  const raw = localStorage.getItem("inventory");
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch (err) {
    return [];
  }
}

function renderInventory(items) {
  inventoryList.innerHTML = items
    .map(it => `<div class="inventory-item">${it.name} — $${it.price.toFixed(2)}</div>`)
    .join("");
}

// ── Reset handler ───────────────────────────────────────────────────────
// Unconditional seed + render + status message. No try/catch, so every
// path through the handler writes the storage key — all_paths_write
// should PASS.

resetInvBtn.addEventListener("click", function () {
  seedInventory();
  const items = loadInventory();
  renderInventory(items);
  inventoryStatus.textContent = "Seeded " + items.length + " items";
});

// ── First-load bootstrap ────────────────────────────────────────────────
// Runs at module load time, not inside any handler — so it doesn't
// affect handler-scoped constraints.

if (!localStorage.getItem("inventory")) {
  seedInventory();
}
renderInventory(loadInventory());
