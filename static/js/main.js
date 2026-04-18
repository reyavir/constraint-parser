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
  "static:no_literal(priceDisplay)",
];

/* ── DOM refs ─────────────────────────────────────────────────────────── */
const input         = document.getElementById("constraint-input");
const parseBtn      = document.getElementById("parse-btn");
const resultsArea   = document.getElementById("results");
const errorBox      = document.getElementById("error-box");
const validationBox = document.getElementById("validation-box");
const tokenCard     = document.getElementById("token-card");
const astCard       = document.getElementById("ast-card");
const typeCard      = document.getElementById("type-card");

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
      renderAST(data.ast);
      renderConstraintType(data.type);
      renderValidation(data.validation);
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
  validationBox.classList.add("hidden");
  resultsArea.classList.add("hidden");
  tokenCard.querySelector(".token-table tbody").innerHTML = "";
  astCard.querySelector(".ast-root").innerHTML = "";
  typeCard.querySelector(".type-body").innerHTML = "";
}

/* ── Validation ───────────────────────────────────────────────────────── */
function renderValidation(v) {
  if (!v || v.valid) {
    validationBox.classList.add("hidden");
    return;
  }

  const parts = [];
  if (v.unknown_elements.length) {
    const chips = v.unknown_elements
      .map(n => `<span class="validation-chip">${escapeHtml(n)}</span>`)
      .join("");
    parts.push(`Unknown element${v.unknown_elements.length > 1 ? "s" : ""}:<div class="validation-chips">${chips}</div>`);
  }
  if (v.unknown_apis.length) {
    const chips = v.unknown_apis
      .map(n => `<span class="validation-chip">${escapeHtml(n)}</span>`)
      .join("");
    parts.push(`Unknown API${v.unknown_apis.length > 1 ? "s" : ""}:<div class="validation-chips">${chips}</div>`);
  }

  validationBox.innerHTML = `
    <div class="validation-header">
      <span class="validation-badge">Unknown identifiers</span>
      <span class="validation-title">These names are not in the approved mapping</span>
    </div>
    <div class="validation-message">${parts.join("<br>")}</div>
  `;
  validationBox.classList.remove("hidden");
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

/* ── Step 2: AST ──────────────────────────────────────────────────────── */
function renderAST(node) {
  const root = astCard.querySelector(".ast-root");
  root.innerHTML = renderASTNode(node, null);
}

/**
 * Recursively render an AST node as an indented tree.
 * `label` is the field name from the parent (e.g. "event", "condition").
 */
function renderASTNode(node, label) {
  if (node === null) {
    return renderLeaf(label, "none", "null");
  }

  // Leaf scalars (primitives inside nodes, not node_type fields)
  // — these come up when a field IS a primitive, not from node_type dispatch
  if (typeof node !== "object") {
    const cls = typeof node === "boolean" ? "bool"
              : typeof node === "number"  ? "number"
              : "string";
    return renderLeaf(label, String(node), cls);
  }

  const { node_type, ...fields } = node;

  // Special leaf nodes: render inline rather than as a subtree
  if (node_type === "ElementRef") {
    return renderLeaf(label, `"${escapeHtml(fields.name)}"`, "element");
  }
  if (node_type === "NumberLiteral") {
    return renderLeaf(label, String(fields.value), "number");
  }
  if (node_type === "StringLiteral") {
    return renderLeaf(label, `"${escapeHtml(fields.value)}"`, "string");
  }
  if (node_type === "NullLiteral") {
    return renderLeaf(label, "null", "null");
  }
  if (node_type === "SetRef") {
    return renderLeaf(label, `${escapeHtml(fields.name)} (set)`, "element");
  }

  // Composite node — render header + children recursively
  const labelHtml = label
    ? `<span class="ast-field-label">${escapeHtml(label)}</span> `
    : "";

  const childrenHtml = Object.entries(fields).map(([key, val]) => {
    // Skip booleans that are false to reduce noise, except for 'negated'
    if (val === false && key !== "negated") return "";
    if (val === null && key !== "guard" && key !== "value_expr" && key !== "params") return "";
    return renderASTNode(val, key);
  }).join("");

  return `
    <div class="ast-node">
      <div class="ast-node-header">
        ${labelHtml}<span class="ast-node-type">${escapeHtml(node_type)}</span>
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

/* ── Step 3: Constraint type ──────────────────────────────────────────── */
function renderConstraintType(t) {
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
