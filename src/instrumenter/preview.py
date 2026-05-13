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

# Match src="/x" or src='/x' — absolute paths only, not URLs or //cdn paths.
_SRC_RE  = re.compile(r"""(\bsrc\s*=\s*["'])(/[^"'>\s]+)(["'])""")
_HREF_RE = re.compile(r"""(\bhref\s*=\s*["'])(/[^"'>\s]+\.css)(["'])""")


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
    """Rewrite absolute src=/href= paths so they resolve under /preview/."""
    encoded = quote(source_dir, safe="")

    def _rewrite(match: re.Match) -> str:
        attr_open, path, attr_close = match.group(1), match.group(2), match.group(3)
        # External URLs (//, http, https) were already excluded by the regex,
        # but double-check defensively in case the regex is widened later.
        if path.startswith(("//", "http://", "https://")):
            return match.group(0)
        new_path = f"/preview{path}?source={encoded}"
        return f"{attr_open}{new_path}{attr_close}"

    html = _SRC_RE.sub(_rewrite, html)
    html = _HREF_RE.sub(_rewrite, html)
    return html
