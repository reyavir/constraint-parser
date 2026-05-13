"""
Lightweight source-walker that lists every DOM id in the user's app.

Replaces the heavier CodeQL + LLM pipeline. Walks HTML and JS files under a
source directory, extracts each `id="..."` (HTML) and `el.id = "..."` (JS),
captures the tag + a human-readable label (from `data-cv-label` on HTML
elements; empty for JS-created ones), and emits the mapping shape the rest
of the system expects:

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
      "apis": {}
    }

API discovery is deliberately left for a future pass — if you write
`call(cartApi)` constraints today, Visitor 2 just skips api validation.
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


def scan_element_ids(source_dir: str) -> dict:
    root = Path(source_dir).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {source_dir}")

    elements: dict[str, dict] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in (".html", ".htm"):
            _scan_html(path, root, elements)
        elif suffix == ".js":
            _scan_js(path, root, elements)

    return {"elements": elements, "apis": {}}


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


def _scan_js(path: Path, root: Path, elements: dict) -> None:
    rel = str(path.relative_to(root))
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        m = _JS_ID_RE.match(line)
        if not m:
            continue
        dom_id = m.group("id")
        if dom_id in elements:
            continue
        elements[dom_id] = {
            "label": "",                        # JS-created elements have no inner text yet
            "tag":   "element",                 # unknown at scan time
            "kind":  "component",               # safe default
            "file":  rel,
            "line":  lineno,
        }
