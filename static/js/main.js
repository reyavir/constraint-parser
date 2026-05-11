/* ── Element reference ────────────────────────────────────────────────── */

async function loadElementReference() {
  try {
    const res  = await fetch("/mapping/elements");
    const data = await res.json();

    const refPanel      = document.getElementById("element-ref");
    const noMappingHint = document.getElementById("no-mapping-hint");
    const refElements   = document.getElementById("ref-elements");
    const refApis       = document.getElementById("ref-apis");
    const refApisRow    = document.getElementById("ref-apis-row");

    if (!data.available) {
      noMappingHint.classList.remove("hidden");
      return;
    }

    // Elements chips
    refElements.innerHTML = data.elements.map(name =>
      `<button class="ref-chip ref-chip-element" data-insert="${escapeAttr(name)}">${escapeHtml(name)}</button>`
    ).join("");

    // API chips
    if (data.apis.length) {
      refApis.innerHTML = data.apis.map(name =>
        `<button class="ref-chip ref-chip-api" data-insert="${escapeAttr(name)}">${escapeHtml(name)}</button>`
      ).join("");
      refApisRow.classList.remove("hidden");
    }

    refPanel.classList.remove("hidden");

    // Click to insert at cursor
    refPanel.querySelectorAll(".ref-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const name  = chip.dataset.insert;
        const start = input.selectionStart;
        const end   = input.selectionEnd;
        const val   = input.value;
        input.value = val.slice(0, start) + name + val.slice(end);
        input.selectionStart = input.selectionEnd = start + name.length;
        input.focus();
      });
    });

  } catch {
    // silently ignore — reference panel is a nice-to-have
  }
}

loadElementReference();

/* ── State ────────────────────────────────────────────────────────────── */
const EXAMPLES = [
  "P(w(cartDisplay) | A(addBtn)) = 1",
  "P(w(cartDisplay, r(cartDisplay) + 1) | A(addBtn)) = 1",
  "P(w(cartDisplay) | ¬A(addBtn)) = 0",
  "P(call(cartApi) | A(addBtn)) = 1",
  "P(w(a) ∧ w(b) | A(submitBtn)) = 1",
  "P(w(a) XOR w(b) | A(toggleBtn)) = 1",
  "P(seq(w(spinner)) < seq(w(results)) | A(searchBtn)) = 1",
  "no_literal(priceDisplay)",
  "hidden_error()",
];

/* ── DOM refs ─────────────────────────────────────────────────────────── */
const input          = document.getElementById("constraint-input");
const parseBtn       = document.getElementById("parse-btn");
const resultsArea    = document.getElementById("results");
const errorBox       = document.getElementById("error-box");
const tokenCard      = document.getElementById("token-card");
const parseTreeCard  = document.getElementById("parse-tree-card");
const astCard        = document.getElementById("ast-card");
const semanticsCard  = document.getElementById("semantics-card");
const typeCard       = document.getElementById("type-card");
const verifyCard    = document.getElementById("verify-card");
const verifyBtn     = document.getElementById("verify-btn");
const verifyDbInput = document.getElementById("verify-db-input");
const verifyResult  = document.getElementById("verify-result");

/* ── Bootstrap ────────────────────────────────────────────────────────── */
document.getElementById("examples-container").innerHTML =
  EXAMPLES.map(ex =>
    `<button class="example-btn" data-ex="${escapeAttr(ex)}">${escapeHtml(ex)}</button>`
  ).join("");

document.querySelectorAll(".example-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    input.value = btn.dataset.ex;
    input.focus();
  });
});

parseBtn.addEventListener("click", runParse);
input.addEventListener("keydown", e => { if (e.key === "Enter") runParse(); });

/* ── Main action ──────────────────────────────────────────────────────── */
async function runParse() {
  const source = input.value.trim();
  if (!source) return;

  setLoading(true);
  clearResults();

  try {
    const res  = await fetch("/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ constraint: source }),
    });
    const data = await res.json();

    if (!data.success) {
      showError(data.error);
    } else {
      renderTokens(data.tokens);
      renderParseTree(data.parse_tree);
      renderAST(data.ast);
      renderConstraintType(data.type);
      renderSemantics(data.semantics);
      renderVerifyCard(data.verifiable);
      resultsArea.classList.remove("hidden");
    }
  } catch (err) {
    showError("Network error — is the server running?");
  } finally {
    setLoading(false);
  }
}

/* ── Loading state ────────────────────────────────────────────────────── */
function setLoading(on) {
  parseBtn.disabled = on;
  parseBtn.innerHTML = on
    ? `<span class="spinner"></span>Parsing…`
    : "Parse";
}

/* ── Error display ────────────────────────────────────────────────────── */
function showError(msg) {
  errorBox.innerHTML = `
    <div class="error-header">
      <span class="error-badge">Invalid</span>
      <span class="error-title">Could not parse constraint</span>
    </div>
    <div class="error-message">${escapeHtml(msg)}</div>
  `;
  errorBox.classList.remove("hidden");
}

function clearResults() {
  errorBox.classList.add("hidden");
  verifyCard.classList.add("hidden");
  verifyResult.classList.add("hidden");
  resultsArea.classList.add("hidden");
  tokenCard.querySelector(".token-table tbody").innerHTML = "";
  parseTreeCard.querySelector(".parse-tree").textContent = "";
  astCard.querySelector(".ast-root").innerHTML = "";
  semanticsCard.querySelector(".semantics-body").innerHTML = "";
  typeCard.querySelector(".type-body").innerHTML = "";
  typeCard.classList.remove("hidden");
}

/* ── Step 4: Semantic analysis (Visitor 2) ────────────────────────────── */
function renderSemantics(sem) {
  const body = semanticsCard.querySelector(".semantics-body");

  if (!sem) {
    body.innerHTML = `
      <div class="semantics-skipped">
        Semantic analysis skipped — no AST.
      </div>`;
    return;
  }

  if (sem.valid) {
    body.innerHTML = `
      <div class="semantics-pass">
        <span class="semantics-pass-badge">Pass</span>
        <span class="semantics-pass-msg">All semantic rules satisfied.</span>
      </div>`;
    return;
  }

  const n = sem.issues.length;
  const rows = sem.issues.map(i => `
    <li>
      <span class="semantic-issue-code">${escapeHtml(i.code)}</span>
      <span class="semantic-issue-msg">${escapeHtml(i.message)}</span>
    </li>
  `).join("");

  body.innerHTML = `
    <div class="semantics-fail-header">
      <span class="semantics-fail-badge">Fail</span>
      <span class="semantics-fail-title">${n} issue${n > 1 ? "s" : ""} found</span>
    </div>
    <ul class="semantic-issues">${rows}</ul>
  `;
}

/* ── Step 1: Tokens ───────────────────────────────────────────────────── */
function renderTokens(tokens) {
  const tbody = tokenCard.querySelector(".token-table tbody");
  tbody.innerHTML = tokens.map(tok => `
    <tr>
      <td><span class="tok-badge tok-${tok.category}">${escapeHtml(tok.kind)}</span></td>
      <td class="tok-value">${escapeHtml(tok.value || "—")}</td>
      <td class="tok-pos">${tok.pos}</td>
    </tr>
  `).join("");
}

/* ── Step 2: Parse tree ───────────────────────────────────────────────── */
function renderParseTree(treeStr) {
  parseTreeCard.querySelector(".parse-tree").textContent = treeStr || "";
}

/* ── Step 3: AST ──────────────────────────────────────────────────────── */
function renderAST(node) {
  const root = astCard.querySelector(".ast-root");
  root.innerHTML = renderASTNode(node, null);
}

/**
 * Recursively render the dict AST as an indented tree.
 * `label` is the field name from the parent (e.g. "event", "condition").
 */
function renderASTNode(node, label) {
  if (node === null || node === undefined) {
    return renderLeaf(label, "none", "null");
  }

  // Plain scalars (string element refs, numbers, booleans inside fields)
  if (typeof node !== "object") {
    const cls = typeof node === "boolean" ? "bool"
              : typeof node === "number"  ? "number"
              : "string";
    const text = typeof node === "string" ? `"${escapeHtml(node)}"` : String(node);
    return renderLeaf(label, text, cls);
  }

  if (Array.isArray(node)) {
    return node.map((item, i) => renderASTNode(item, `${label ?? ""}[${i}]`)).join("");
  }

  const { type, ...fields } = node;

  // LiteralExpr collapses to a single inline value
  if (type === "LiteralExpr") {
    const v = fields.value;
    if (v === "null")           return renderLeaf(label, "null", "null");
    if (typeof v === "boolean") return renderLeaf(label, String(v), "bool");
    if (typeof v === "number")  return renderLeaf(label, String(v), "number");
    return renderLeaf(label, `"${escapeHtml(String(v))}"`, "string");
  }

  // Composite node — header + children
  const labelHtml = label
    ? `<span class="ast-field-label">${escapeHtml(label)}</span> `
    : "";

  const childrenHtml = Object.entries(fields).map(([key, val]) => {
    if (val === false && key !== "negated") return "";
    if (val === null && key !== "guard" && key !== "value_expr" && key !== "params") return "";
    return renderASTNode(val, key);
  }).join("");

  return `
    <div class="ast-node">
      <div class="ast-node-header">
        ${labelHtml}<span class="ast-node-type">${escapeHtml(type ?? "Unknown")}</span>
      </div>
      ${childrenHtml}
    </div>
  `;
}

function renderLeaf(label, value, cls) {
  const labelHtml = label
    ? `<span class="ast-leaf-label">${escapeHtml(label)}</span>`
    : "";
  return `
    <div class="ast-leaf">
      ${labelHtml}
      <span class="ast-val-${cls}">${value}</span>
    </div>
  `;
}

/* ── Step 4: Constraint type ──────────────────────────────────────────── */
function renderConstraintType(t) {
  if (!t) {
    // Classifier (visitor 2) not wired yet — hide the card entirely.
    typeCard.classList.add("hidden");
    return;
  }
  typeCard.classList.remove("hidden");
  const body = typeCard.querySelector(".type-body");
  body.innerHTML = `
    <span class="type-badge type-${t.color}">${escapeHtml(t.label)}</span>

    <div class="type-info-grid">
      <div class="type-info-block">
        <span class="type-info-label">Verification approach</span>
        <span class="type-info-value">${escapeHtml(t.summary)}</span>
      </div>
      <div class="type-info-block">
        <span class="type-info-label">Checker function</span>
        <div class="type-checker-box">${escapeHtml(t.checker)}</div>
      </div>
    </div>

    <p class="type-detail">${escapeHtml(t.detail)}</p>
  `;
}

/* ── Step 5: Verify ───────────────────────────────────────────────────── */

function renderVerifyCard(verifiable) {
  if (verifiable) {
    verifyCard.classList.remove("hidden");
    verifyResult.classList.add("hidden");
  } else {
    verifyCard.classList.add("hidden");
  }
}

verifyBtn.addEventListener("click", async () => {
  const source  = input.value.trim();
  const db_path = verifyDbInput.value.trim();
  if (!source) return;

  verifyBtn.disabled  = true;
  verifyBtn.innerHTML = `<span class="spinner"></span>Verifying…`;
  verifyResult.classList.add("hidden");

  try {
    const res  = await fetch("/verify", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ constraint: source, db_path }),
    });
    const data = await res.json();

    if (!data.success) {
      verifyResult.className   = "verify-result verify-fail";
      verifyResult.innerHTML   = `
        <div class="verify-header">
          <span class="verify-badge verify-badge-fail">Error</span>
          <span class="verify-title">${escapeHtml(data.error)}</span>
        </div>`;
    } else if (data.passed) {
      verifyResult.className = "verify-result verify-pass";
      verifyResult.innerHTML = `
        <div class="verify-header">
          <span class="verify-badge verify-badge-pass">Passed</span>
          <span class="verify-title">No violations found</span>
        </div>`;
    } else {
      const chips = data.violations
        .map(v => `<span class="verify-violation">${escapeHtml(v.file)}:${v.line}</span>`)
        .join("");
      verifyResult.className = "verify-result verify-fail";
      verifyResult.innerHTML = `
        <div class="verify-header">
          <span class="verify-badge verify-badge-fail">Failed</span>
          <span class="verify-title">${data.violations.length} silent error${data.violations.length > 1 ? "s" : ""} found</span>
        </div>
        <div class="verify-violations">${chips}</div>`;
    }
    verifyResult.classList.remove("hidden");

  } catch {
    verifyResult.className = "verify-result verify-fail";
    verifyResult.innerHTML = `
      <div class="verify-header">
        <span class="verify-badge verify-badge-fail">Error</span>
        <span class="verify-title">Network error — is the server running?</span>
      </div>`;
    verifyResult.classList.remove("hidden");
  } finally {
    verifyBtn.disabled  = false;
    verifyBtn.innerHTML = "Run Verification";
  }
});

/* ── Utilities ────────────────────────────────────────────────────────── */
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
