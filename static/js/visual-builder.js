/* ─────────────────────────────────────────────────────────────────────────
 * visual-builder.js
 *
 * Drives the Visual Builder tab:
 *   • "Open preview" → new browser tab pointed at /preview/<entry>?source=<dir>
 *   • Polls /constraints/list while the tab is visible and active so newly
 *     received constraints from the overlay appear within ~3s.
 *   • "Load into parser" copies the formula into the Parser tab's input and
 *     switches tabs — no server round-trip.
 *   • "Clear all" calls /constraints/clear.
 *
 * Loaded last in templates/index.html so all refs and the tab-switching
 * helper (mapping.js) are guaranteed to exist.
 * ─────────────────────────────────────────────────────────────────────── */

(function () {
  const sourceInput = document.getElementById("preview-source-input");
  const entryInput  = document.getElementById("preview-entry-input");
  const openBtn     = document.getElementById("open-preview-btn");
  const clearBtn    = document.getElementById("clear-inbox-btn");
  const inboxList   = document.getElementById("inbox-list");
  const inboxEmpty  = document.getElementById("inbox-empty");
  const parserInput = document.getElementById("constraint-input");

  if (!openBtn || !inboxList) return;  // tab not present

  let pollTimer  = null;
  let lastSerial = "";   // skip re-render if the list didn't change

  // ── Open preview ────────────────────────────────────────────────────
  openBtn.addEventListener("click", () => {
    const source = sourceInput.value.trim();
    const entry  = (entryInput.value.trim() || "index.html");
    if (!source) return;
    const url = `/preview/${encodeURIComponent(entry)}?source=${encodeURIComponent(source)}`;
    window.open(url, "_blank");
  });

  // ── Clear inbox ─────────────────────────────────────────────────────
  clearBtn.addEventListener("click", async () => {
    if (!confirm("Clear all imported constraints?")) return;
    await fetch("/constraints/clear", { method: "POST" });
    refreshInbox(/*force*/ true);
  });

  // ── Fetch + render ─────────────────────────────────────────────────
  async function refreshInbox(force) {
    try {
      const res  = await fetch("/constraints/list");
      const data = await res.json();
      const items = data.constraints || [];
      const serial = items.length + ":" + items.map(c => c.created_at).join(",");
      if (!force && serial === lastSerial) return;
      lastSerial = serial;
      renderInbox(items);
    } catch {
      /* silent — this is a poll */
    }
  }

  function renderInbox(items) {
    if (items.length === 0) {
      inboxEmpty.style.display = "";
      inboxList.innerHTML = "";
      return;
    }
    inboxEmpty.style.display = "none";

    inboxList.innerHTML = items.map((c, i) => {
      const labels = (c.targets || []).map(t => t.label || t.id).join(", ");
      return `
        <div class="inbox-item">
          <div class="inbox-formula">${escapeHtml(c.constraint)}</div>
          <div class="inbox-meta">
            <span class="inbox-meta-label">action:</span> ${escapeHtml((c.action || {}).label || "—")}
            <span class="inbox-meta-sep">·</span>
            <span class="inbox-meta-label">targets:</span> ${escapeHtml(labels || "—")}
          </div>
          <div class="inbox-actions">
            <button class="btn-load" data-idx="${i}">Load into parser</button>
          </div>
        </div>`;
    }).join("");

    inboxList.querySelectorAll(".btn-load").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.idx);
        loadIntoParser(items[idx].constraint);
      });
    });
  }

  function loadIntoParser(formula) {
    if (parserInput) parserInput.value = formula;
    const parserTabBtn = document.querySelector('.tab-btn[data-tab="parser"]');
    if (parserTabBtn) parserTabBtn.click();
    if (parserInput) parserInput.focus();
  }

  // ── Polling — only while tab is visible AND active ──────────────────
  function isBuilderActive() {
    const panel = document.getElementById("tab-builder");
    return panel && !panel.classList.contains("hidden");
  }

  function startPolling() {
    refreshInbox();
    if (pollTimer) return;
    pollTimer = setInterval(refreshInbox, 3000);
  }
  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }
  function updatePolling() {
    if (document.visibilityState === "visible" && isBuilderActive()) startPolling();
    else stopPolling();
  }

  document.addEventListener("visibilitychange", updatePolling);
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => setTimeout(updatePolling, 0));
  });

  // Initial state — refresh once even if the tab isn't visible, so when the
  // user switches in they see a populated list immediately.
  refreshInbox();
  updatePolling();

  // ── utils ──────────────────────────────────────────────────────────
  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
