(function () {
  'use strict';

  // Mapping is substituted at injection time by runner.py.
  //   { "elements": { "<dom-id>": { label, tag, kind, file, line }, ... },
  //     "apis":     { "<name>":   { endpoint, ... } | {} } }
  const __mapping = __MAPPING__;

  // Active trace state — reset/collected from Python via page.evaluate.
  window.__traceId      = null;
  window.__traces       = [];      // event log for the current trace
  window.__valuesBefore = {};      // snapshot taken at __resetTrace()
  window.__errors       = [];      // js errors + http errors for the current trace
  let __seq = 0;

  // ── Helpers ──────────────────────────────────────────────────────────────

  // Map every event back to a mapping key. Mapping keys ARE the DOM ids,
  // so the lookup is direct — no selector indirection.
  function __nameForElement(el) {
    if (!el || !el.id) return null;
    return Object.prototype.hasOwnProperty.call(__mapping.elements || {}, el.id)
      ? el.id
      : null;
  }

  // Same shape as before for fetch URLs: prefer a symbolic api name when
  // the mapping has one, otherwise fall back to the raw URL string.
  const __endpointToName = {};
  for (const [name, info] of Object.entries(__mapping.apis || {})) {
    if (info && info.endpoint) __endpointToName[info.endpoint] = name;
  }
  function __nameForEndpoint(url) {
    const stripped = String(url).split('?')[0];
    for (const [endpoint, name] of Object.entries(__endpointToName)) {
      if (stripped === endpoint || stripped.endsWith(endpoint)) return name;
    }
    return String(url);
  }

  function __push(event) {
    event.seq = __seq++;
    event.timestamp = Date.now();
    window.__traces.push(event);
  }

  function __readCurrentValue(el) {
    if (!el) return null;
    if ('value' in el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT')) {
      return String(el.value);
    }
    return el.textContent != null ? String(el.textContent).trim() : null;
  }

  // ── Public API used by runner.py via page.evaluate() ─────────────────────

  window.__resetTrace = function (traceId) {
    window.__traceId      = traceId;
    window.__traces       = [];
    window.__errors       = [];
    __seq                 = 0;

    // Snapshot the current value of every mapped element. Missing elements
    // record `null` so downstream consumers can distinguish "absent" from
    // "empty string".
    const snapshot = {};
    for (const id of Object.keys(__mapping.elements || {})) {
      const el = document.getElementById(id);
      snapshot[id] = el ? __readCurrentValue(el) : null;
    }
    window.__valuesBefore = snapshot;
  };

  window.__collectTrace = function () {
    return {
      id:            window.__traceId,
      events:        window.__traces.slice(),
      values_before: window.__valuesBefore,
      errors:        window.__errors.slice(),
    };
  };

  // ── DOM write interception ───────────────────────────────────────────────

  function __patchSetter(proto, prop) {
    const desc = Object.getOwnPropertyDescriptor(proto, prop);
    if (!desc || !desc.set) return;
    const original = desc.set;
    Object.defineProperty(proto, prop, {
      set(val) {
        const name = __nameForElement(this);
        if (name !== null) {
          __push({ type: 'write', element: name, property: prop, value: String(val) });
        }
        return original.call(this, val);
      },
      get: desc.get,
      configurable: true,
      enumerable: desc.enumerable,
    });
  }

  __patchSetter(Node.prototype,             'textContent');
  __patchSetter(Element.prototype,          'innerHTML');
  __patchSetter(HTMLElement.prototype,      'innerText');
  __patchSetter(HTMLInputElement.prototype, 'value');

  // ── User-action interception ─────────────────────────────────────────────

  ['click', 'submit', 'change', 'input'].forEach(function (eventName) {
    document.addEventListener(eventName, function (e) {
      const name = __nameForElement(e.target);
      if (name !== null) {
        __push({ type: 'action', element: name, event_name: eventName });
      }
    }, true); // capture phase — runs before any page handler
  });

  // ── Network interception ─────────────────────────────────────────────────

  const __origFetch = window.fetch;
  window.fetch = function (input, init) {
    const url    = typeof input === 'string' ? input : (input && input.url) || String(input);
    const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    const apiRef = __nameForEndpoint(url);

    __push({ type: 'api_call', api_ref: apiRef, endpoint: url, method: method });

    return __origFetch.apply(this, arguments).then(function (resp) {
      __push({
        type:     'api_response',
        api_ref:  apiRef,
        endpoint: url,
        method:   method,
        status:   resp.status,
        ok:       resp.ok,
      });
      if (!resp.ok) {
        window.__errors.push({
          kind:     'http_error',
          url:      url,
          method:   method,
          status:   resp.status,
        });
      }
      return resp;
    }).catch(function (err) {
      window.__errors.push({
        kind:    'fetch_failed',
        url:     url,
        method:  method,
        message: String(err && err.message || err),
      });
      throw err;
    });
  };

  // ── Error capture ────────────────────────────────────────────────────────

  window.addEventListener('error', function (e) {
    window.__errors.push({
      kind:    'js_error',
      message: e.message,
      source:  e.filename,
      line:    e.lineno,
    });
  });

  window.addEventListener('unhandledrejection', function (e) {
    window.__errors.push({
      kind:    'unhandled_rejection',
      message: String(e.reason && e.reason.message || e.reason),
    });
  });

})();
