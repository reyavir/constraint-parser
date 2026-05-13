"""
Inject stable IDs (cv_0001, cv_0002, …) into UI elements across the user's
source so later CodeQL queries can pinpoint each element from a constraint
identifier.

HTML pass — BeautifulSoup walks each .html file and adds an `id` to a narrow
visual subset of tags. `<div>` is special-cased: only tagged when it's a leaf
(no block-level children) or when it behaves like a button (onclick / role).

JS pass — regex match `(const|let|var) name = document.createElement(...)`
and insert `name.id = "cv_NNNN";` on the next line unless `name.id =`
already appears within the next ~3 lines.

  Known gap: createElement calls with no assigned variable are skipped
  e.g. `parent.appendChild(document.createElement('div'))`
  These elements won't get an id and can't be referenced in constraints.

Idempotency — scans every file first to find the highest existing cv_<n>
and starts the counter at max+1. Re-runs add IDs only to newly-introduced
elements without ever colliding with prior ones.

Safety — if `source_dir` is not a git repo, every modified file is copied
to `<file>.bak` before being rewritten.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup


ID_PREFIX = "cv_"

# Interactive — can appear inside A(ei)
_INTERACTIVE = {"button", "input", "select", "textarea", "a"}
# Display — can appear inside w(ej) / r(ej)
_DISPLAY     = {"span", "p", "h1", "h2", "h3", "h4", "li", "td", "label"}
# Block-level tags whose presence disqualifies a <div> from being tagged.
_BLOCK       = {"div", "section", "article", "nav", "header", "footer",
                "main", "ul", "ol", "table"}

_TAGS_TO_ID = _INTERACTIVE | _DISPLAY | {"div"}

_ID_RE = re.compile(rf"{re.escape(ID_PREFIX)}(\d+)")
_JS_RE = re.compile(
    r"^(?P<indent>\s*)(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*"
    r"=\s*document\.createElement\([^)]+\)\s*;?\s*$"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def repo_status(source_dir: str) -> dict:
    """Inspect *source_dir* without modifying anything. The UI calls this to
    decide whether to show the no-git confirmation banner."""
    root = Path(source_dir).expanduser().resolve()
    return {
        "exists": root.is_dir(),
        "is_git": (root / ".git").is_dir(),
        "path":   str(root),
    }


def inject_ids(source_dir: str, *, force_backup: bool | None = None) -> dict:
    """
    Walk *source_dir*, tag every HTML/JS UI element that doesn't have an id.

    force_backup
        None  → auto: backup iff not a git repo
        True  → always write .bak files
        False → never write .bak files (caller has confirmed)
    """
    root = Path(source_dir).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {source_dir}")

    is_git    = (root / ".git").is_dir()
    do_backup = (not is_git) if force_backup is None else force_backup

    counter    = _next_counter(root)
    changed:    list[str] = []
    backups:    list[str] = []
    html_added = 0
    js_added   = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".html":
            added = _process_html(path, counter, do_backup, backups)
        elif suffix == ".js":
            added = _process_js(path, counter, do_backup, backups)
        else:
            continue
        if added:
            counter += added
            if suffix == ".html":
                html_added += added
            else:
                js_added += added
            changed.append(str(path.relative_to(root)))

    return {
        "files_changed":  changed,
        "html_ids_added": html_added,
        "js_ids_added":   js_added,
        "total_added":    html_added + js_added,
        "is_git":         is_git,
        "backups_made":   backups,
    }


# ---------------------------------------------------------------------------
# HTML — narrow subset, <div> special-cased
# ---------------------------------------------------------------------------

def _should_tag_div(tag) -> bool:
    """Only tag <div> when it's a leaf or behaves like a button."""
    has_block_children = any(
        getattr(child, "name", None) in _BLOCK for child in tag.children
    )
    has_click = tag.get("onclick") is not None or tag.get("role") == "button"
    return (not has_block_children) or has_click


_LABEL_MAX = 30


def _derive_label(tag) -> str:
    """First non-empty text snippet for a tag, trimmed and length-capped."""
    raw = tag.get_text(" ", strip=True)
    return raw[:_LABEL_MAX] if raw else ""


def _process_html(path: Path, counter_start: int,
                  do_backup: bool, backups: list[str]) -> int:
    soup = BeautifulSoup(path.read_text(), "html.parser")

    added   = 0
    touched = False
    for tag in soup.find_all(True):
        if tag.name not in _TAGS_TO_ID:
            continue
        # Add id only when missing — never overwrite the app's own ids.
        if not tag.has_attr("id"):
            if tag.name == "div" and not _should_tag_div(tag):
                continue
            tag["id"] = f"{ID_PREFIX}{counter_start + added:04d}"
            added  += 1
            touched = True
        # Always (re-)derive a label so renames in source flow into the mapping.
        # Skip elements where we never added an id AND no inner text exists.
        if not tag.has_attr("data-cv-label"):
            label = _derive_label(tag)
            if label:
                tag["data-cv-label"] = label
                touched = True

    if touched:
        if do_backup:
            _backup(path, backups)
        path.write_text(str(soup))
    return added


# ---------------------------------------------------------------------------
# JS — regex match on `const|let|var name = document.createElement(...)`
# ---------------------------------------------------------------------------

def _process_js(path: Path, counter_start: int,
                do_backup: bool, backups: list[str]) -> int:
    lines = path.read_text().splitlines()
    out:   list[str] = []
    added = 0

    for i, line in enumerate(lines):
        out.append(line)
        m = _JS_RE.match(line)
        if not m:
            continue
        name   = m["name"]
        indent = m["indent"]
        # Idempotency guard — skip if `.id` is already set near the createElement.
        if any(re.match(rf"\s*{re.escape(name)}\s*\.\s*id\s*=", l)
               for l in lines[i + 1 : i + 4]):
            continue
        out.append(f'{indent}{name}.id = "{ID_PREFIX}{counter_start + added:04d}";')
        added += 1

    if added > 0:
        if do_backup:
            _backup(path, backups)
        path.write_text("\n".join(out) + "\n")
    return added


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backup(path: Path, backups: list[str]) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)
        backups.append(str(bak))


def _next_counter(root: Path) -> int:
    """Highest existing cv_<n> across all .html/.js files, plus one."""
    highest = 0
    for path in root.rglob("*"):
        if path.suffix.lower() not in (".html", ".js"):
            continue
        try:
            text = path.read_text()
        except Exception:
            continue
        for m in _ID_RE.finditer(text):
            highest = max(highest, int(m.group(1)))
    return highest + 1
