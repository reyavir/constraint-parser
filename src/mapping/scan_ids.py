"""
Lightweight source-walker that lists every DOM id, API call, and storage
usage in the user's app.

Walks HTML and JS files under a source directory and emits:

    {
      "elements": {
        "<dom-id>": {
          "label": "<human-readable name>",
          "tag":   "<html tag>",
          "kind":  "action" | "component",
          "file":  "<relative path>",
          "line":  <int>,
        },
        ...
      },

      "apis": {
        "<derived-id>": {
          "endpoint": "/api/cart",
          "method":   "POST" | "GET" | ...,
          "file":     "<relative path>",
          "line":     <int>,
        },
        ...
      },

      "storage": {
        "<derived-id>": {
          "area": "localStorage" | "sessionStorage",
          "key":  "<key string>",
          "ops":  ["setItem", "getItem", "removeItem"],
          "file": "<relative path>",
          "line": <int>,
        },
        ...
      },
    }

Derived identifiers (used as the mapping keys) are stable, grammar-safe names:
   /api/cart                -> cartApi
   /api/checkout            -> checkoutApi
   /api/search?q=...        -> searchApi
   localStorage 'last_event'-> lastEventStorage

Only the path is used to derive an API name — query strings are ignored,
so `/api/search?q=x` and `/api/search?q=y` both map to `searchApi`. The
first sighting of an endpoint wins for the file/line attribution.
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup


_ACTION_TAGS = {"button", "input", "a", "select", "textarea", "form"}

# Match `el.id = "..."` or `el.id = '...'` — same shape inject_ids writes.
_JS_ID_RE = re.compile(
    r"""^(?P<indent>\s*)(?P<name>[A-Za-z_$][\w$]*)\s*\.\s*id\s*=\s*['"](?P<id>[^'"]+)['"]"""
)

# fetch("..."). The options object (if any) is parsed separately, by
# scanning a fixed window of characters after the URL — regex can't
# balance nested braces (e.g. `headers: { ... }`), so we just look
# for the first `method: "..."` declaration in the next _METHOD_SCAN
# characters and fall back to GET if we don't find one.
_FETCH_RE = re.compile(r"""fetch\s*\(\s*['"](?P<url>[^'"]+)['"]""")
_METHOD_IN_OPTS_RE = re.compile(r"""method\s*:\s*['"](?P<m>[A-Za-z]+)['"]""")
_METHOD_SCAN = 400

# axios.get("...") / axios.post("...") / ... (no axios() bare form)
_AXIOS_RE = re.compile(
    r"""axios\s*\.\s*(?P<method>get|post|put|delete|patch|head)\s*\(\s*['"](?P<url>[^'"]+)['"]""",
    re.IGNORECASE,
)

# localStorage.setItem("k", ...) / .getItem("k") / .removeItem("k")
# Same for sessionStorage.
_STORAGE_RE = re.compile(
    r"""(?P<area>local|session)Storage\s*\.\s*(?P<op>getItem|setItem|removeItem)\s*"""
    r"""\(\s*['"](?P<key>[^'"]+)['"]""",
)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def scan_element_ids(source_dir: str) -> dict:
    root = Path(source_dir).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {source_dir}")

    elements: dict[str, dict] = {}
    apis:     dict[str, dict] = {}
    storage:  dict[str, dict] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in (".html", ".htm"):
            _scan_html(path, root, elements)
        elif suffix == ".js":
            _scan_js(path, root, elements, apis, storage)

    return {"elements": elements, "apis": apis, "storage": storage}


# ─────────────────────────────────────────────────────────────────────────────
# Scanners
# ─────────────────────────────────────────────────────────────────────────────

def _scan_html(path: Path, root: Path, elements: dict) -> None:
    soup = BeautifulSoup(path.read_text(), "html.parser")
    rel  = str(path.relative_to(root))

    for tag in soup.find_all(True):
        if not tag.has_attr("id"):
            continue
        dom_id = tag["id"]
        if dom_id in elements:                   # first sighting wins
            continue
        elements[dom_id] = {
            "label": tag.get("data-cv-label") or tag.get_text(" ", strip=True)[:30] or "",
            "tag":   tag.name,
            "kind":  "action" if tag.name in _ACTION_TAGS else "component",
            "file":  rel,
            "line":  tag.sourceline or 0,
        }


def _scan_js(path: Path, root: Path, elements: dict, apis: dict, storage: dict) -> None:
    rel = str(path.relative_to(root))
    lines = path.read_text().splitlines()
    full = "\n".join(lines)

    # ── DOM ids assigned in JS (single-line matches only) ────────────────
    for lineno, line in enumerate(lines, start=1):
        m = _JS_ID_RE.match(line)
        if not m:
            continue
        dom_id = m.group("id")
        if dom_id in elements:
            continue
        elements[dom_id] = {
            "label": "",
            "tag":   "element",
            "kind":  "component",
            "file":  rel,
            "line":  lineno,
        }

    # ── fetch() calls ────────────────────────────────────────────────────
    for m in _FETCH_RE.finditer(full):
        url    = m.group("url")
        method = "GET"
        window = full[m.end(): m.end() + _METHOD_SCAN]
        if window.lstrip().startswith(","):     # has an options object
            mm = _METHOD_IN_OPTS_RE.search(window)
            if mm:
                method = mm.group("m").upper()
        _record_api(apis, url=url, method=method, file=rel,
                    line=_lineno_at(full, m.start()))

    # ── axios.METHOD() calls ─────────────────────────────────────────────
    for m in _AXIOS_RE.finditer(full):
        _record_api(apis, url=m.group("url"), method=m.group("method").upper(),
                    file=rel, line=_lineno_at(full, m.start()))

    # ── localStorage / sessionStorage ────────────────────────────────────
    for m in _STORAGE_RE.finditer(full):
        _record_storage(storage,
                        area=f"{m.group('area')}Storage",
                        key=m.group("key"),
                        op=m.group("op"),
                        file=rel,
                        line=_lineno_at(full, m.start()))


# ─────────────────────────────────────────────────────────────────────────────
# Recorders
# ─────────────────────────────────────────────────────────────────────────────

def _record_api(apis: dict, *, url: str, method: str, file: str, line: int) -> None:
    # Strip the query string for derivation + dedup; keep the path-only form
    # as the canonical endpoint to display.
    path_only = url.split("?", 1)[0]
    name = _api_name_from_url(path_only)
    if name in apis:
        return                       # first sighting wins
    apis[name] = {
        "endpoint": path_only,
        "method":   method,
        "file":     file,
        "line":     line,
    }


def _record_storage(storage: dict, *, area: str, key: str, op: str,
                    file: str, line: int) -> None:
    name = _storage_name_from_key(key)
    entry = storage.get(name)
    if entry is None:
        storage[name] = {
            "area": area,
            "key":  key,
            "ops":  [op],
            "file": file,
            "line": line,
        }
    elif op not in entry["ops"]:
        entry["ops"].append(op)


# ─────────────────────────────────────────────────────────────────────────────
# Identifier derivation
# ─────────────────────────────────────────────────────────────────────────────

def _api_name_from_url(path: str) -> str:
    """
    /api/cart                  -> cartApi
    /api/checkout              -> checkoutApi
    /api/users/profile         -> usersProfileApi
    /search                    -> searchApi
    /                          -> rootApi
    """
    pieces = [p for p in path.strip("/").split("/") if p and p != "api"]
    if not pieces:
        return "rootApi"
    head, *tail = pieces
    parts = [_lower_camel(head)] + [_upper_camel(p) for p in tail]
    name  = "".join(parts) + "Api"
    return _sanitize_identifier(name)


def _storage_name_from_key(key: str) -> str:
    """
    'last_event'      -> lastEventStorage
    'cart'            -> cartStorage
    'user-settings'   -> userSettingsStorage
    """
    return _sanitize_identifier(_lower_camel(key) + "Storage")


_WORD_BOUNDARY = re.compile(r"[^A-Za-z0-9]+")

def _split_words(s: str) -> list[str]:
    return [w for w in _WORD_BOUNDARY.split(s) if w]

def _lower_camel(s: str) -> str:
    words = _split_words(s)
    if not words:
        return ""
    head, *tail = words
    return head.lower() + "".join(w.capitalize() for w in tail)

def _upper_camel(s: str) -> str:
    return "".join(w.capitalize() for w in _split_words(s))

def _sanitize_identifier(name: str) -> str:
    # IDENTIFIER grammar: [a-zA-Z][a-zA-Z0-9_-]*. Camelcasing already
    # produces a valid identifier, but defend against leading digits or
    # totally-empty derivations.
    if not name or not name[0].isalpha():
        name = "x" + name
    return re.sub(r"[^A-Za-z0-9_-]", "", name) or "anonymousApi"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _lineno_at(text: str, char_idx: int) -> int:
    """1-based line number for a character offset into *text*."""
    return text.count("\n", 0, char_idx) + 1
