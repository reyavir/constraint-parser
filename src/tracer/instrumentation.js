(function () {
  'use strict';

  // Injected at runtime by runner.py — maps constraint names to element info
  const __mapping = __MAPPING__;

  window.__traces = [];
  let __seq = 0;

  // ── Reverse lookup tables ─────────────────────────────────────────────

  // "#add-to-cart-btn" -> "addToCartBtn"
  const __selectorToName = {};
  for (const [name, info] of Object.entries(__mapping.elements || {})) {
    if (info.selector) __selectorToName[info.selector] = name;
  }

  // "/api/cart" -> "cartApi"
  const __endpointToName = {};
  for (const [name, info] of Object.entries(__mapping.apis || {})) {
    if (info.endpoint) __endpointToName[info.endpoint] = name;
  }

  function __nameForElement(el) {
    if (!el || !el.id) return null;
    return __selectorToName['#' + el.id] || null;
  }

  function __nameForEndpoint(url) {
    const str = String(url).split('?')[0]; // strip query string for lookup
    for (const [endpoint, name] of Object.entries(__endpointToName)) {
      if (str === endpoint || str.endsWith(endpoint)) return name;
    }
    return String(url); // fallback to raw URL
  }

  function __push(event) {
    event.seq = __seq++;
    event.timestamp = Date.now();
    window.__traces.push(event);
  }

  // ── Intercept DOM property writes ─────────────────────────────────────

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
  __patchSetter(Element.prototype,          'innerText');
  __patchSetter(HTMLInputElement.prototype, 'value');

  // ── Intercept user actions ────────────────────────────────────────────

  ['click', 'submit', 'change', 'input'].forEach(function (eventName) {
    document.addEventListener(eventName, function (e) {
      const name = __nameForElement(e.target);
      if (name !== null) {
        __push({ type: 'action', element: name, event_name: eventName });
      }
    }, true); // capture phase — fires before any page handler
  });

  // ── Intercept fetch ───────────────────────────────────────────────────

  const __origFetch = window.fetch;
  window.fetch = function (input, init) {
    const url    = typeof input === 'string' ? input : (input && input.url) || String(input);
    const method = (init && init.method) || (input && input.method) || 'GET';
    __push({
      type:     'api_call',
      api_ref:  __nameForEndpoint(url),
      endpoint: url,
      method:   method.toUpperCase(),
    });
    return __origFetch.apply(this, arguments);
  };

})();
