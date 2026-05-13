/* ─────────────────────────────────────────────────────────────────────────
 * constraint-builder.js
 *
 * Self-contained overlay for visually building constraints over a running
 * web app. Inject via a single <script> tag — the panel appears in the
 * top-right corner of the page.
 *
 * Workflow:
 *   1. Click "Select action" → pick the element that triggers the behaviour
 *      (a button, input, …). Cursor turns into a crosshair; hovering shows
 *      a dashed outline; clicking captures `e.target.id`.
 *   2. Click "+ Add target" → pick one or more elements that should change
 *      as a result of the action.
 *   3. Click "Save constraint" → the constraint string
 *        P(w(target1) AND w(target2) … | A(action)) = 1
 *      is built automatically and appended to the saved list.
 *   4. Switch to the Review tab and click "Export JSON" to download every
 *      saved constraint along with its human-readable labels.
 *
 * Element IDs (e.g. `cv_0001`) are required on every clickable element —
 * generate them with the project's `inject_ids` pre-processing step.
 * Display labels are derived from `innerText` and are purely cosmetic.
 *
 * Implementation notes:
 *   • Single IIFE, no globals other than `window.__constraintBuilder`.
 *   • All highlighting / click capture is torn down when selection mode
 *     exits or the user hits Escape.
 *   • Saved constraints persist across reloads via localStorage.
 *   • All UI styles are scoped to `#__constraint_builder_panel` and its
 *     descendants — the app's own CSS is untouched.
 * ─────────────────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  if (window.__constraintBuilder) {
    console.warn('[constraint-builder] already initialised — skipping');
    return;
  }

  // ── Constants ─────────────────────────────────────────────────────────
  const PANEL_ID    = '__constraint_builder_panel';
  const STYLE_ID    = '__constraint_builder_styles';
  const STORAGE_KEY = '__constraint_builder_saved';
  const HL_COLOR    = '#4A90E2';
  const LABEL_MAX   = 25;

  // ── State ─────────────────────────────────────────────────────────────
  const state = {
    action:       null,     // { id, label } | null
    targets:      [],       // [{ id, label }]
    saved:        [],       // [{ constraint, action, targets, created_at }]
    mode:         'build',  // 'build' | 'review'
    status:       null,     // { kind: 'error' | 'info', text }
    selecting:    false,    // selection mode active?
    confirmClear: false,    // "Clear all" two-click confirmation latch
  };

  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state.saved)); }
    catch (e) { /* private mode etc — drop silently */ }
  }
  function restore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      state.saved = raw ? JSON.parse(raw) : [];
    } catch (e) { state.saved = []; }
  }

  // ── Display labels ────────────────────────────────────────────────────
  // Prefer the data-cv-label baked in during preprocessing — those are
  // stable. Fall back to live innerText when the element wasn't tagged.
  function getDisplayLabel(el) {
    const baked = (el.dataset && el.dataset.cvLabel) || '';
    const text  = baked || (el.innerText || '').trim().slice(0, LABEL_MAX);
    return text ? `${el.id} (${text})` : el.id;
  }

  // ── Constraint formula ────────────────────────────────────────────────
  function buildConstraint(actionId, targetIds) {
    if (!actionId || targetIds.length === 0) return null;
    const writes = targetIds.map(id => `w(${id})`).join(' AND ');
    return `P(${writes} | A(${actionId})) = 1`;
  }

  // ── Styles (scoped to the panel) ──────────────────────────────────────
  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${PANEL_ID} {
        position: fixed;
        top: 16px;
        right: 16px;
        width: 340px;
        max-height: calc(100vh - 32px);
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        box-shadow: 0 10px 32px rgba(15,23,42,0.18);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
        font-size: 13px;
        line-height: 1.45;
        color: #1e293b;
        z-index: 999999;
        display: flex;
        flex-direction: column;
      }
      #${PANEL_ID} * { box-sizing: border-box; }

      #${PANEL_ID} .__cb_header {
        background: ${HL_COLOR};
        color: #fff;
        padding: 8px 12px;
        border-radius: 7px 7px 0 0;
        cursor: move;
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-weight: 600;
        user-select: none;
      }
      #${PANEL_ID} .__cb_close {
        cursor: pointer;
        font-size: 16px;
        line-height: 1;
        padding: 2px 6px;
        border-radius: 4px;
      }
      #${PANEL_ID} .__cb_close:hover { background: rgba(255,255,255,0.18); }

      #${PANEL_ID} .__cb_tabs {
        display: flex;
        border-bottom: 1px solid #e2e8f0;
      }
      #${PANEL_ID} .__cb_tabs button {
        flex: 1;
        padding: 8px 10px;
        background: #f8fafc;
        border: none;
        border-right: 1px solid #e2e8f0;
        cursor: pointer;
        font: inherit;
        color: #475569;
        font-weight: 500;
      }
      #${PANEL_ID} .__cb_tabs button:last-child { border-right: none; }
      #${PANEL_ID} .__cb_tabs button._active {
        background: #ffffff;
        color: #1e293b;
        font-weight: 600;
        box-shadow: inset 0 -2px 0 ${HL_COLOR};
      }

      #${PANEL_ID} .__cb_body {
        padding: 12px;
        overflow-y: auto;
        flex: 1;
      }
      #${PANEL_ID} .__cb_section_label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .07em;
        text-transform: uppercase;
        color: #64748b;
        margin: 0 0 6px 0;
      }
      #${PANEL_ID} .__cb_section { margin-bottom: 14px; }

      #${PANEL_ID} .__cb_chip {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        padding: 6px 8px;
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 5px;
        margin-bottom: 4px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 12px;
        word-break: break-all;
      }
      #${PANEL_ID} .__cb_chip ._remove {
        cursor: pointer;
        color: #94a3b8;
        font-weight: 700;
        padding: 0 4px;
        flex-shrink: 0;
      }
      #${PANEL_ID} .__cb_chip ._remove:hover { color: #dc2626; }

      #${PANEL_ID} .__cb_empty {
        font-size: 12px;
        color: #94a3b8;
        font-style: italic;
        margin-bottom: 6px;
      }

      #${PANEL_ID} .__cb_btn {
        font: inherit;
        background: #ffffff;
        border: 1px solid #cbd5e1;
        color: #1e293b;
        padding: 6px 12px;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
      }
      #${PANEL_ID} .__cb_btn:hover { background: #f1f5f9; }
      #${PANEL_ID} .__cb_btn._primary {
        background: ${HL_COLOR};
        color: #fff;
        border-color: ${HL_COLOR};
      }
      #${PANEL_ID} .__cb_btn._primary:hover { background: #3a7bc8; }
      #${PANEL_ID} .__cb_btn._danger {
        background: #ffffff;
        color: #b91c1c;
        border-color: #fca5a5;
      }
      #${PANEL_ID} .__cb_btn._danger:hover { background: #fef2f2; }
      #${PANEL_ID} .__cb_btn:disabled { opacity: .5; cursor: not-allowed; }
      #${PANEL_ID} .__cb_btn._small { padding: 4px 10px; font-size: 12px; }

      #${PANEL_ID} .__cb_btn_row { display: flex; gap: 6px; }

      #${PANEL_ID} .__cb_preview {
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 12px;
        background: #0f172a;
        color: #f1f5f9;
        padding: 8px 10px;
        border-radius: 6px;
        white-space: pre-wrap;
        word-break: break-all;
        margin-bottom: 8px;
        min-height: 38px;
      }
      #${PANEL_ID} .__cb_preview._empty { color: #64748b; font-family: inherit; font-style: italic; }

      #${PANEL_ID} .__cb_status {
        padding: 7px 12px;
        border-top: 1px solid #e2e8f0;
        font-size: 12px;
      }
      #${PANEL_ID} .__cb_status._error { color: #b91c1c; background: #fef2f2; }
      #${PANEL_ID} .__cb_status._info  { color: #1e40af; background: #eff6ff; }

      #${PANEL_ID} .__cb_saved_item {
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 6px;
      }
      #${PANEL_ID} .__cb_saved_head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
      }
      #${PANEL_ID} .__cb_saved_idx {
        font-size: 11px;
        color: #64748b;
        font-weight: 600;
      }
      #${PANEL_ID} .__cb_saved_formula {
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 11.5px;
        word-break: break-all;
      }
      #${PANEL_ID} .__cb_saved_labels {
        font-size: 11px;
        color: #64748b;
        margin-top: 4px;
      }

      /* Highlight applied to the user's elements during selection mode */
      .__cb_highlight {
        outline: 2px dashed ${HL_COLOR} !important;
        outline-offset: 2px !important;
      }
    `;
    document.head.appendChild(style);
  }

  // ── Panel construction ────────────────────────────────────────────────
  let panel;
  function buildPanel() {
    panel = document.createElement('div');
    panel.id = PANEL_ID;
    document.body.appendChild(panel);
  }

  // ── Rendering ─────────────────────────────────────────────────────────
  function render() {
    if (!panel) return;
    panel.innerHTML = `
      <div class="__cb_header" data-role="drag">
        <span>Constraint Builder</span>
        <span class="__cb_close" data-action="close" title="Close">×</span>
      </div>
      <div class="__cb_tabs">
        <button data-action="mode" data-mode="build"  class="${state.mode === 'build'  ? '_active' : ''}">Build</button>
        <button data-action="mode" data-mode="review" class="${state.mode === 'review' ? '_active' : ''}">Review (${state.saved.length})</button>
      </div>
      <div class="__cb_body">
        ${state.mode === 'build' ? renderBuild() : renderReview()}
      </div>
      ${renderStatus()}
    `;

    // Wire up event delegation each render (innerHTML wipes listeners).
    panel.addEventListener('click', onPanelClick);
    const header = panel.querySelector('.__cb_header');
    if (header) header.addEventListener('mousedown', startDrag);
  }

  function renderBuild() {
    const a  = state.action;
    const ts = state.targets;
    const preview = buildConstraint(a && a.id, ts.map(t => t.id));

    const actionRow = a
      ? `<div class="__cb_chip">
           <span>${escapeHtml(a.label)}</span>
           <span class="_remove" data-action="clear_action" title="Remove">×</span>
         </div>`
      : `<div class="__cb_empty">No action selected.</div>`;

    const targetRows = ts.length
      ? ts.map((t, i) => `
          <div class="__cb_chip">
            <span>${escapeHtml(t.label)}</span>
            <span class="_remove" data-action="remove_target" data-idx="${i}" title="Remove">×</span>
          </div>`).join('')
      : `<div class="__cb_empty">No targets yet.</div>`;

    const canSave = !!(a && ts.length);
    const previewBlock = preview
      ? `<div class="__cb_preview">${escapeHtml(preview)}</div>`
      : `<div class="__cb_preview _empty">Pick an action and at least one target to see the preview.</div>`;

    const selecting = state.selecting;
    return `
      <div class="__cb_section">
        <div class="__cb_section_label">Action  A(eᵢ)</div>
        ${actionRow}
        <div class="__cb_btn_row" style="margin-top:6px;">
          <button class="__cb_btn _small" data-action="pick_action" ${selecting ? 'disabled' : ''}>
            ${a ? 'Replace action' : 'Select action'}
          </button>
        </div>
      </div>

      <div class="__cb_section">
        <div class="__cb_section_label">Targets  w(eⱼ)</div>
        ${targetRows}
        <div class="__cb_btn_row" style="margin-top:6px;">
          <button class="__cb_btn _small" data-action="pick_target" ${selecting ? 'disabled' : ''}>+ Add target</button>
        </div>
      </div>

      <div class="__cb_section">
        <div class="__cb_section_label">Preview</div>
        ${previewBlock}
        <button class="__cb_btn _primary" data-action="save" ${canSave ? '' : 'disabled'}>Save constraint</button>
      </div>
    `;
  }

  function renderReview() {
    if (state.saved.length === 0) {
      return `<div class="__cb_empty">No saved constraints yet. Build one in the Build tab.</div>`;
    }
    const items = state.saved.map((c, i) => {
      const labelLine = c.targets.map(t => t.label).join(', ');
      return `
        <div class="__cb_saved_item">
          <div class="__cb_saved_head">
            <span class="__cb_saved_idx">#${i + 1}</span>
            <span class="_remove" data-action="remove_saved" data-idx="${i}" title="Delete">×</span>
          </div>
          <div class="__cb_saved_formula">${escapeHtml(c.constraint)}</div>
          <div class="__cb_saved_labels">action: ${escapeHtml(c.action.label)} → ${escapeHtml(labelLine)}</div>
        </div>`;
    }).join('');
    const clearLabel = state.confirmClear ? 'Confirm clear' : 'Clear all';
    return `
      ${items}
      <div class="__cb_btn_row" style="margin-top:8px;">
        <button class="__cb_btn _primary" data-action="send">Send to app</button>
        <button class="__cb_btn"          data-action="export">Export JSON</button>
        <button class="__cb_btn _danger"  data-action="clear">${clearLabel}</button>
      </div>
    `;
  }

  function renderStatus() {
    const s = state.status;
    if (!s) return '';
    return `<div class="__cb_status _${s.kind}">${escapeHtml(s.text)}</div>`;
  }

  function setStatus(kind, text) {
    state.status = { kind, text };
    render();
    // Auto-clear info messages after a few seconds; keep errors until next action.
    if (kind === 'info') {
      setTimeout(() => {
        if (state.status && state.status.text === text) {
          state.status = null;
          render();
        }
      }, 2500);
    }
  }

  // ── Event handlers ────────────────────────────────────────────────────
  function onPanelClick(e) {
    const target = e.target.closest('[data-action]');
    if (!target) return;
    const action = target.dataset.action;

    switch (action) {
      case 'close':
        panel.style.display = 'none';
        break;
      case 'mode':
        state.mode = target.dataset.mode;
        state.status = null;
        render();
        break;
      case 'pick_action':
        startSelection(el => {
          if (!el) return;                                 // cancelled
          state.action = { id: el.id, label: getDisplayLabel(el) };
          render();
        });
        break;
      case 'clear_action':
        state.action = null;
        render();
        break;
      case 'pick_target':
        startSelection(el => {
          if (!el) return;
          if (state.targets.some(t => t.id === el.id)) {
            setStatus('error', `Target ${el.id} is already in the list.`);
            return;
          }
          state.targets.push({ id: el.id, label: getDisplayLabel(el) });
          render();
        });
        break;
      case 'remove_target':
        state.targets.splice(Number(target.dataset.idx), 1);
        render();
        break;
      case 'save':
        saveConstraint();
        break;
      case 'remove_saved':
        state.saved.splice(Number(target.dataset.idx), 1);
        persist();
        render();
        break;
      case 'export':
        exportJSON();
        break;
      case 'send':
        sendToApp();
        break;
      case 'clear':
        clearAll();
        break;
    }
  }

  // Two-click confirmation (no alert/prompt/confirm allowed).
  let _clearTimer = null;
  function clearAll() {
    if (state.saved.length === 0) {
      setStatus('error', 'Nothing to clear.');
      return;
    }
    if (!state.confirmClear) {
      state.confirmClear = true;
      setStatus('info', 'Click "Confirm clear" again to delete every saved constraint.');
      clearTimeout(_clearTimer);
      _clearTimer = setTimeout(() => {
        state.confirmClear = false;
        render();
      }, 4000);
      render();
      return;
    }
    clearTimeout(_clearTimer);
    state.confirmClear = false;
    state.saved = [];
    persist();
    setStatus('info', 'All saved constraints cleared.');
  }

  function saveConstraint() {
    const a  = state.action;
    const ts = state.targets;
    const formula = buildConstraint(a && a.id, ts.map(t => t.id));
    if (!formula) {
      setStatus('error', 'Pick an action and at least one target before saving.');
      return;
    }
    state.saved.push({
      constraint: formula,
      action:     { id: a.id, label: a.label },
      targets:    ts.map(t => ({ id: t.id, label: t.label })),
      created_at: new Date().toISOString(),
    });
    persist();
    state.action  = null;
    state.targets = [];
    setStatus('info', 'Saved. Switch to Review to see all constraints.');
  }

  function exportJSON() {
    const payload = JSON.stringify({ version: 1, constraints: state.saved }, null, 2);
    const blob = new Blob([payload], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = `constraints-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // Same-origin POST — overlay runs on /preview/* served by the same Flask app
  // that exposes /constraints/import, so no CORS config is needed.
  function sendToApp() {
    if (state.saved.length === 0) {
      setStatus('error', 'No saved constraints to send.');
      return;
    }
    fetch('/constraints/import', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ version: 1, constraints: state.saved }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.success) {
          setStatus('info', `Sent ${data.added} new constraint(s) · inbox total ${data.total}.`);
        } else {
          setStatus('error', data.error || 'Server rejected the payload.');
        }
      })
      .catch(() => setStatus('error', 'Network error — is the app server reachable?'));
  }

  // ── Selection mode ────────────────────────────────────────────────────
  let selectionContext = null;

  function startSelection(callback) {
    if (state.selecting) return;
    state.selecting = true;
    state.status = { kind: 'info', text: 'Click an element to select it · Esc to cancel.' };
    render();

    const prevCursor = document.body.style.cursor;
    document.body.style.cursor = 'crosshair';

    let lastHL = null;
    const clearHL = () => {
      if (lastHL) { lastHL.classList.remove('__cb_highlight'); lastHL = null; }
    };

    function onMouseOver(e) {
      if (panel.contains(e.target)) { clearHL(); return; }
      clearHL();
      lastHL = e.target;
      lastHL.classList.add('__cb_highlight');
    }

    function onClick(e) {
      if (panel.contains(e.target)) return;       // let panel clicks work normally
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      const el = e.target;
      if (!el.id) {
        setStatus('error', `Element <${(el.tagName || '').toLowerCase()}> has no id. Run inject_ids on your source first.`);
        // stay in selection mode so the user can try another element
        return;
      }
      cleanup();
      callback(el);
    }

    function onKey(e) {
      if (e.key === 'Escape') {
        cleanup();
        callback(null);                            // signal cancellation
      }
    }

    function cleanup() {
      document.body.style.cursor = prevCursor;
      clearHL();
      document.removeEventListener('mouseover', onMouseOver, true);
      document.removeEventListener('click',     onClick,     true);
      document.removeEventListener('keydown',   onKey,       true);
      state.selecting = false;
      state.status = null;
      selectionContext = null;
      render();
    }

    document.addEventListener('mouseover', onMouseOver, true);
    document.addEventListener('click',     onClick,     true);
    document.addEventListener('keydown',   onKey,       true);
    selectionContext = { cleanup };
  }

  // ── Drag ─────────────────────────────────────────────────────────────
  function startDrag(e) {
    // Don't start a drag from the close button or anything else with an action.
    if (e.target.closest('[data-action]')) return;

    const rect = panel.getBoundingClientRect();
    const offX = e.clientX - rect.left;
    const offY = e.clientY - rect.top;

    function move(ev) {
      const x = Math.max(0, Math.min(window.innerWidth  - rect.width,  ev.clientX - offX));
      const y = Math.max(0, Math.min(window.innerHeight - rect.height, ev.clientY - offY));
      panel.style.left  = x + 'px';
      panel.style.top   = y + 'px';
      panel.style.right = 'auto';
    }
    function up() {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup',   up);
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup',   up);
    e.preventDefault();
  }

  // ── Utilities ────────────────────────────────────────────────────────
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Init ──────────────────────────────────────────────────────────────
  function init() {
    injectStyles();
    buildPanel();
    restore();
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  // ── Public hooks (testing / programmatic use) ─────────────────────────
  window.__constraintBuilder = {
    state,
    render,
    save:   saveConstraint,
    export: exportJSON,
    reset:  () => { state.saved = []; persist(); render(); },
    cancelSelection: () => selectionContext && selectionContext.cleanup(),
  };
})();
