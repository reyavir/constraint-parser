"""
Element-mapping path constants + load helper.

The mapping itself is produced by `scan_element_ids` in scan_ids.py —
a lightweight source walk that lists every DOM id and label. The
heavyweight CodeQL + LLM pipeline that used to live here was removed
when `inject_ids` + the overlay made it redundant.
"""

from __future__ import annotations

import json
from pathlib import Path


MAPPING_FILE = Path("element_mapping.json")


def load_mapping(path: Path = MAPPING_FILE) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Element mapping not found at '{path}'. "
            "Open the Element Mapping tab and click 'Refresh element list' first."
        )
    with path.open() as f:
        return json.load(f)
