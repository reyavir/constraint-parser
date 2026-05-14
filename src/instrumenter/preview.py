"""
HTML rewrite helpers for the in-app preview route.

When the user's app is served at /preview/<path>?source=<dir>:

* inject_script(html)
    Adds `<script src="/static/js/constraint-builder.js">` so the overlay
    appears automatically. Handles vibe-coded HTML — falls back to </html>
    then plain append if </body> is missing.

* rewrite_absolute_paths(html, source_dir)
    Rewrites absolute `src="/foo.js"` and `href="/foo.css"` to point at the
    preview route, so apps that load assets via absolute paths keep working
    (otherwise many would render blank because /foo.js would hit Flask
    instead of the user's source).
"""

from __future__ import annotations

import re
from urllib.parse import quote


_OVERLAY_TAG = '<script src="/static/js/constraint-builder.js"></script>'

# Match every src= and href= value (relative OR absolute). External URLs,
# fragments, and other non-navigable schemes are filtered out inside the
# rewriter rather than at the regex level.
_ATTR_RE = re.compile(r"""(\b(?:src|href)\s*=\s*["'])([^"'>]+)(["'])""")

_SKIP_PREFIXES = (
    "//",         # protocol-relative
    "http://",
    "https://",
    "data:",
    "blob:",
    "mailto:",
    "tel:",
    "javascript:",
    "#",          # pure fragment
)


def inject_script(html: str) -> str:
    """Add the overlay script tag to *html*, with fallbacks for malformed input."""
    if _OVERLAY_TAG in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", f"{_OVERLAY_TAG}\n</body>", 1)
    if "</html>" in html:
        return html.replace("</html>", f"{_OVERLAY_TAG}\n</html>", 1)
    return html + f"\n{_OVERLAY_TAG}\n"


def rewrite_absolute_paths(html: str, source_dir: str) -> str:
    """
    Rewrite every src=/href= so the browser routes it back through
    /preview/...?source=<dir>:

        href="style.css"      → href="/preview/style.css?source=<dir>"
        src="./cart.js"       → src="/preview/cart.js?source=<dir>"
        src="js/util.js"      → src="/preview/js/util.js?source=<dir>"
        href="/x.css"         → href="/preview/x.css?source=<dir>"
        href="page.html#bar"  → href="/preview/page.html?source=<dir>#bar"
        href="https://x.com"  → unchanged
        href="#section"       → unchanged
    """
    encoded = quote(source_dir, safe="")

    def _rewrite(match: re.Match) -> str:
        attr_open, value, attr_close = match.group(1), match.group(2), match.group(3)
        if value.startswith(_SKIP_PREFIXES):
            return match.group(0)

        # Preserve fragment verbatim — it goes after the query string.
        path, frag = value, ""
        if "#" in path:
            path, frag_part = path.split("#", 1)
            frag = f"#{frag_part}"

        # Strip leading "./" so we don't end up with /preview/./foo
        if path.startswith("./"):
            path = path[2:]

        if path.startswith("/"):
            new_path = f"/preview{path}"
        else:
            new_path = f"/preview/{path}"

        return f"{attr_open}{new_path}?source={encoded}{frag}{attr_close}"

    return _ATTR_RE.sub(_rewrite, html)
