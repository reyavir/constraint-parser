"""
Element mapping pipeline.

Three stages:
  1. Run CodeQL queries to scan the codebase (codeql_runner)
  2. Call LLM to generate a draft mapping             (generator)
  3. Write the draft file for the user to review      (this module)

Usage
-----
    from src.mapping import generate_element_mapping
    generate_element_mapping(db_path="./codeql-db")

    # User edits element_mapping.json, then constraints can be written.
"""

from __future__ import annotations

import json
from pathlib import Path

from .codeql_runner import collect_raw_elements
from .generator import generate_draft_mapping

MAPPING_FILE = Path("element_mapping.json")


def generate_element_mapping(db_path: str = "./codeql-db") -> Path:
    """
    Run the full pipeline and write a draft mapping file.

    Returns the path to the written file.
    Raises if CodeQL is not installed or the database does not exist.
    """
    print("Step 1: scanning codebase with CodeQL...")
    raw = collect_raw_elements(db_path)

    print("Step 2: generating draft mapping with LLM...")
    draft = generate_draft_mapping(raw)

    print("Step 3: writing mapping file for user review...")
    _write_mapping(draft)

    return MAPPING_FILE


def load_mapping(path: Path = MAPPING_FILE) -> dict:
    """
    Load and return the approved mapping file.

    Raises FileNotFoundError if the mapping has not been generated yet,
    reminding callers that the mapping must exist before constraints can
    be written.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Element mapping not found at '{path}'. "
            "Run generate_element_mapping() first, then review and approve the file."
        )
    with path.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_mapping(draft: dict) -> None:
    with MAPPING_FILE.open("w") as f:
        json.dump(draft, f, indent=2)

    print(f"Draft mapping written to {MAPPING_FILE}")
    print("Please review and rename elements before writing constraints.")
