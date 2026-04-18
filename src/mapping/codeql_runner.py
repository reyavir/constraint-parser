"""
Stage 1: run the four CodeQL queries and return their raw results.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

QUERIES_DIR = Path(__file__).parent.parent.parent / "queries"
TMP_DIR     = Path("/tmp/codeql-results")


def run_query(db_path: str, query_file: str) -> list[dict]:
    """
    Run a single CodeQL query against *db_path* and return the result rows.

    Each row is a dict whose keys match the ``as <name>`` aliases in the
    SELECT clause of the query.

    CodeQL query run produces a binary BQRS file; a second decode step
    converts it to JSON.
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    bqrs_path = TMP_DIR / f"{query_file}.bqrs"
    json_path = TMP_DIR / f"{query_file}.json"

    # Step 1: run query → binary BQRS
    result = subprocess.run(
        [
            "codeql", "query", "run",
            str(QUERIES_DIR / query_file),
            "--database", db_path,
            "--output", str(bqrs_path),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise RuntimeError(f"CodeQL query failed ({query_file}):\n{stderr}")

    # Step 2: decode BQRS → JSON
    result = subprocess.run(
        [
            "codeql", "bqrs", "decode",
            "--format=json",
            "--output", str(json_path),
            str(bqrs_path),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise RuntimeError(f"CodeQL bqrs decode failed ({query_file}):\n{stderr}")

    # JSON structure: {"#select": {"columns": [...], "tuples": [[...], ...]}}
    with json_path.open() as f:
        data = json.load(f)

    select  = data.get("#select", {})
    columns = [col["name"] for col in select.get("columns", [])]
    tuples  = select.get("tuples", [])

    return [dict(zip(columns, row)) for row in tuples]


def collect_raw_elements(db_path: str) -> dict:
    """
    Run all four queries and return a dict with keys:
      actions, displays, apis, errors
    """
    print("  Running action_elements.ql ...")
    actions = run_query(db_path, "action_elements.ql")

    print("  Running display_elements.ql ...")
    displays = run_query(db_path, "display_elements.ql")

    print("  Running api_calls.ql ...")
    apis = run_query(db_path, "api_calls.ql")

    print("  Running error_handlers.ql ...")
    errors = run_query(db_path, "error_handlers.ql")

    return {
        "actions":  actions,
        "displays": displays,
        "apis":     apis,
        "errors":   errors,
    }
