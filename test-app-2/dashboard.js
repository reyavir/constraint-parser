(function () {
  "use strict";

  /** @typedef {{ id: string, customer: string, items: string, amount: number, status: 'pending'|'completed'|'cancelled', date: string }} Order */

  /** @type {Order[]} */
  const ORDERS = [
    { id: "o1", customer: "Avery Chen", items: "Desk lamp, USB hub", amount: 89.5, status: "completed", date: "2026-05-01" },
    { id: "o2", customer: "Jordan Mills", items: "Monitor 27\"", amount: 349.99, status: "pending", date: "2026-05-02" },
    { id: "o3", customer: "Sam Rivera", items: "Wireless mouse", amount: 45.0, status: "completed", date: "2026-05-02" },
    { id: "o4", customer: "Taylor Brooks", items: "Keyboard, wrist rest", amount: 178.25, status: "cancelled", date: "2026-05-03" },
    { id: "o5", customer: "Avery Chen", items: "Webcam HD", amount: 129.0, status: "completed", date: "2026-05-04" },
    { id: "o6", customer: "Riley Park", items: "Standing desk frame", amount: 520.0, status: "pending", date: "2026-05-05" },
    { id: "o7", customer: "Morgan Lee", items: "Noise-cancelling headphones", amount: 299.0, status: "completed", date: "2026-05-06" },
    { id: "o8", customer: "Casey Nguyen", items: "Laptop stand", amount: 62.4, status: "completed", date: "2026-05-07" },
    { id: "o9", customer: "Jordan Mills", items: "HDMI cables (2)", amount: 24.99, status: "pending", date: "2026-05-08" },
    { id: "o10", customer: "Quinn Foster", items: "Ergonomic chair", amount: 449.0, status: "cancelled", date: "2026-05-09" },
    { id: "o11", customer: "Riley Park", items: "Desk mat", amount: 38.0, status: "completed", date: "2026-05-10" },
    { id: "o12", customer: "Sam Rivera", items: "SSD 1TB", amount: 94.99, status: "completed", date: "2026-05-11" },
  ];

  const $ = (id) => document.getElementById(id);

  const elRevenue = $("stat-total-revenue");
  const elCount = $("stat-order-count");
  const elAov = $("stat-avg-order-value");
  const elSearch = $("customer-search");
  const elFrom = $("date-from");
  const elTo = $("date-to");
  const elStatus = $("status-filter");
  const elBody = $("orders-table-body");
  const elEmpty = $("orders-empty");
  const elClear = $("clear-filters-btn");

  function formatMoney(n) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
  }

  /**
   * @param {string} ymd
   * @returns {number} UTC midnight timestamp for that calendar day
   */
  function parseYmd(ymd) {
    const [y, m, d] = ymd.split("-").map(Number);
    return Date.UTC(y, m - 1, d);
  }

  /**
   * @param {Order[]} list
   */
  function applyFilters(list) {
    const q = (elSearch.value || "").trim().toLowerCase();
    const fromVal = elFrom.value;
    const toVal = elTo.value;
    const statusVal = elStatus.value;

    const fromTs = fromVal ? parseYmd(fromVal) : null;
    const toTs = toVal ? parseYmd(toVal) + 86400000 : null;

    return list.filter((o) => {
      if (q && !o.customer.toLowerCase().includes(q)) return false;
      const ts = parseYmd(o.date);
      if (fromTs !== null && ts < fromTs) return false;
      if (toTs !== null && ts >= toTs) return false;
      if (statusVal && o.status !== statusVal) return false;
      return true;
    });
  }

  /**
   * @param {Order[]} filtered
   */
  function updateStats(filtered) {
    const count = filtered.length;
    const revenue = filtered.reduce((s, o) => s + o.amount, 0);
    const aov = count > 0 ? revenue / count : 0;

    elRevenue.textContent = formatMoney(revenue);
    elCount.textContent = String(count);
    elAov.textContent = formatMoney(aov);

    elRevenue.setAttribute("data-cv-label", elRevenue.textContent);
    elCount.setAttribute("data-cv-label", elCount.textContent);
    elAov.setAttribute("data-cv-label", elAov.textContent);
  }

  /**
   * @param {Order[]} filtered
   */
  function renderTable(filtered) {
    elBody.replaceChildren();
    if (filtered.length === 0) {
      elEmpty.hidden = false;
      return;
    }
    elEmpty.hidden = true;

    const frag = document.createDocumentFragment();
    for (const o of filtered) {
      const tr = document.createElement("tr");
      tr.id = "cv_0001";
      tr.dataset.orderId = o.id;

      const tdName = document.createElement("td");
      tdName.id = "cv_0002";
      tdName.textContent = o.customer;
      tdName.setAttribute("data-cv-label", o.customer);

      const tdItems = document.createElement("td");
      tdItems.id = "cv_0003";
      tdItems.textContent = o.items;
      tdItems.setAttribute("data-cv-label", o.items);

      const tdAmt = document.createElement("td");
      tdAmt.id = "cv_0004";
      tdAmt.className = "amount";
      tdAmt.textContent = formatMoney(o.amount);
      tdAmt.setAttribute("data-cv-label", tdAmt.textContent);

      const tdStatus = document.createElement("td");
      tdStatus.id = "cv_0005";
      const span = document.createElement("span");
      span.id = "cv_0006";
      span.className = `status status-${o.status}`;
      span.textContent = o.status;
      span.setAttribute("data-cv-label", o.status);
      tdStatus.appendChild(span);

      tr.append(tdName, tdItems, tdAmt, tdStatus);
      frag.appendChild(tr);
    }
    elBody.appendChild(frag);
  }

  function refresh() {
    const filtered = applyFilters(ORDERS);
    const opt = elStatus.selectedOptions[0];
    elStatus.setAttribute("data-cv-label", opt ? opt.textContent.trim() : "");
    const q = (elSearch.value || "").trim();
    elSearch.setAttribute("data-cv-label", q || elSearch.placeholder || "");
    elFrom.setAttribute("data-cv-label", elFrom.value || "");
    elTo.setAttribute("data-cv-label", elTo.value || "");
    updateStats(filtered);
    renderTable(filtered);
  }

  function clearFilters() {
    elSearch.value = "";
    elFrom.value = "";
    elTo.value = "";
    elStatus.value = "";
    refresh();
  }

  [elSearch, elFrom, elTo, elStatus].forEach((el) => {
    el.addEventListener("input", refresh);
    el.addEventListener("change", refresh);
  });
  elClear.addEventListener("click", clearFilters);

  refresh();
})();
