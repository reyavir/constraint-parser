/* ── Tab switching ─────────────────────────────────────────────────────── */

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.add("hidden"));
  document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add("active");
  document.getElementById("tab-" + tabName).classList.remove("hidden");
}

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// "Go to mapping tab" link in the no-mapping hint
document.getElementById("go-to-mapping-btn")?.addEventListener("click", () => {
  switchTab("mapping");
});

/* ── DOM refs ─────────────────────────────────────────────────────────── */

const dbPathInput       = document.getElementById("db-path-input");
const scanBtn           = document.getElementById("scan-btn");
const scanLogCard       = document.getElementById("scan-log-card");
const scanLog           = document.getElementById("scan-log");
const mappingResultCard = document.getElementById("mapping-result-card");
const mappingErrorBox   = document.getElementById("mapping-error-box");
const approveBtn        = document.getElementById("approve-btn");
const approveStatus     = document.getElementById("approve-status");

const elementsTableBody = document.querySelector("#elements-table tbody");
const apisTableBody     = document.querySelector("#apis-table tbody");
const errorsTableBody   = document.querySelector("#errors-table tbody");

/* ── Scan & Generate ──────────────────────────────────────────────────── */

scanBtn.addEventListener("click", async () => {
  const dbPath = dbPathInput.value.trim();
  if (!dbPath) return;

  // Reset state
  scanLogCard.classList.remove("hidden");
  mappingResultCard.classList.add("hidden");
  mappingErrorBox.classList.add("hidden");
  scanLog.innerHTML = "";
  approveStatus.textContent = "";

  setScanLoading(true);

  try {
    const res  = await fetch("/mapping/generate", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ db_path: dbPath }),
    });
    const data = await res.json();

    if (!res.ok) {
      showMappingError(data.error || "Failed to start scan.");
      setScanLoading(false);
      return;
    }

    // Poll for completion
    pollStatus();

  } catch {
    showMappingError("Network error — is the server running?");
    setScanLoading(false);
  }
});

let _pollTimer = null;

function pollStatus() {
  _pollTimer = setInterval(async () => {
    try {
      const res  = await fetch("/mapping/status");
      const data = await res.json();

      // Update log
      scanLog.innerHTML = data.log
        .map(line => `<div class="log-line">${escapeHtml(line)}</div>`)
        .join("");
      scanLog.scrollTop = scanLog.scrollHeight;

      if (data.status === "done") {
        clearInterval(_pollTimer);
        setScanLoading(false);
        renderDraftMapping(data.result);
      } else if (data.status === "error") {
        clearInterval(_pollTimer);
        setScanLoading(false);
        showMappingError(data.error || "Unknown error during scan.");
      }
    } catch {
      clearInterval(_pollTimer);
      setScanLoading(false);
      showMappingError("Lost connection to server while polling.");
    }
  }, 1500);
}

/* ── Render draft mapping ─────────────────────────────────────────────── */

// Holds the current draft so Approve can read it
let _currentDraft = null;

function renderDraftMapping(draft) {
  _currentDraft = draft;

  // Elements
  elementsTableBody.innerHTML = Object.entries(draft.elements || {})
    .map(([name, el]) => `
      <tr data-original-name="${escapeAttr(name)}">
        <td>
          <input
            class="name-input"
            type="text"
            value="${escapeAttr(name)}"
            data-key="element"
            data-original="${escapeAttr(name)}"
          />
        </td>
        <td class="mono">${escapeHtml(el.selector || "—")}</td>
        <td class="mono">${escapeHtml(el.tag || "—")}</td>
        <td>
          <span class="kind-badge kind-${el.kind || "action"}">
            ${escapeHtml(el.kind || "—")}
          </span>
        </td>
        <td class="mono muted">
          ${el.kind === "action"
            ? escapeHtml((el.events || []).join(", ") || "—")
            : escapeHtml(el.read_property || "—")}
        </td>
        <td class="muted file-cell">${escapeHtml(el.file || "—")}:${el.line ?? ""}</td>
      </tr>
    `)
    .join("");

  // APIs
  apisTableBody.innerHTML = Object.entries(draft.apis || {})
    .map(([name, api]) => `
      <tr data-original-name="${escapeAttr(name)}">
        <td>
          <input
            class="name-input"
            type="text"
            value="${escapeAttr(name)}"
            data-key="api"
            data-original="${escapeAttr(name)}"
          />
        </td>
        <td class="mono">${escapeHtml(api.endpoint || "—")}</td>
        <td class="mono">${escapeHtml(api.method || "—")}</td>
        <td class="muted file-cell">${escapeHtml(api.file || "—")}:${api.line ?? ""}</td>
      </tr>
    `)
    .join("");

  // Error handlers
  errorsTableBody.innerHTML = (draft.error_handlers || [])
    .map(e => `
      <tr>
        <td class="muted file-cell">${escapeHtml(e.file || "—")}</td>
        <td class="mono muted">${e.line ?? "—"}</td>
      </tr>
    `)
    .join("");

  mappingResultCard.classList.remove("hidden");
}

/* ── Approve & Save ───────────────────────────────────────────────────── */

approveBtn.addEventListener("click", async () => {
  if (!_currentDraft) return;

  // Rebuild mapping with any renamed keys
  const finalMapping = {
    elements:       {},
    apis:           {},
    error_handlers: _currentDraft.error_handlers || [],
  };

  document.querySelectorAll(".name-input[data-key='element']").forEach(input => {
    const original = input.dataset.original;
    const newName  = input.value.trim() || original;
    finalMapping.elements[newName] = _currentDraft.elements[original];
  });

  document.querySelectorAll(".name-input[data-key='api']").forEach(input => {
    const original = input.dataset.original;
    const newName  = input.value.trim() || original;
    finalMapping.apis[newName] = _currentDraft.apis[original];
  });

  approveBtn.disabled = true;
  approveStatus.textContent = "Saving…";

  try {
    const res  = await fetch("/mapping/approve", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ mapping: finalMapping }),
    });
    const data = await res.json();

    if (res.ok) {
      approveStatus.textContent = `Saved to ${data.path}`;
      approveStatus.className   = "approve-status approve-ok";
      loadElementReference();  // refresh parser tab reference panel
    } else {
      approveStatus.textContent = data.error || "Save failed.";
      approveStatus.className   = "approve-status approve-err";
    }
  } catch {
    approveStatus.textContent = "Network error.";
    approveStatus.className   = "approve-status approve-err";
  } finally {
    approveBtn.disabled = false;
  }
});

/* ── Helpers ──────────────────────────────────────────────────────────── */

function setScanLoading(on) {
  scanBtn.disabled   = on;
  scanBtn.innerHTML  = on
    ? `<span class="spinner"></span>Scanning…`
    : "Scan &amp; Generate";
}

function showMappingError(msg) {
  mappingErrorBox.innerHTML = `
    <div class="error-header">
      <span class="error-badge">Error</span>
      <span class="error-title">Scan failed</span>
    </div>
    <div class="error-message">${escapeHtml(msg)}</div>
  `;
  mappingErrorBox.classList.remove("hidden");
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return String(str).replace(/"/g, "&quot;");
}
