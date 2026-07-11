# Constraint Verification for Vibe-Coded Web Apps

A tool for authoring and statically verifying behavioral constraints over
LLM-generated web applications. Users click through their running app to
author constraints (e.g. *"clicking add-to-cart must update the cart
count"*); the tool compiles each constraint to a set of CodeQL queries
that run against the app source and report pass/fail with source-level
evidence.

## What this is

Constraints are written in a small DSL of the form
`P(event | condition) = 1|0` — for example, `P(w(cartCount) | A(addBtn)) = 1`
asserts that clicking `addBtn` always writes to `cartCount`. The tool
compiles the constraint through an ANTLR grammar and an AST walker into
a set of primitive CodeQL queries that check reachability, universal
writing, dataflow sources, storage persistence, and related properties
over the compiled JavaScript database.

## Requirements

- Python 3.10+
- [CodeQL CLI](https://codeql.github.com/docs/codeql-cli/) on your `PATH`
- ANTLR4 (only needed if you modify `Constraint.g4` and want to
  regenerate the parser)

## Setup

```bash
pip install -r requirements.txt
```

Verify CodeQL is installed and available:

```bash
codeql --version
```

## Running

```bash
python run.py
```

Starts the local Flask app on `http://localhost:5050`. Open a test app
in your browser, then use the injected overlay to click through and
author constraints against it.

## Repository layout

- `Constraint.g4`, `src/parser/` — constraint DSL grammar and AST visitor
- `src/constraints/` — classifier, semantic analysis, and constraint types
- `src/static_checks.py` — CodeQL primitive dispatcher (event-side walker,
  probability handling, iterative-deepening for interprocedural checks)
- `queries/` — CodeQL primitive templates (`path_exists.ql`,
  `all_paths_write.ql`, `source_set.ql`, `no_other_handlers.ql`, etc.)
- `src/mapping/` — HTML/JS scanner (`scan_ids.py`) and synthetic-id
  injector (`inject_ids.py`) that build the identifier mapping
- `test-app-<name>/` and `test-app-<name>-modified/` — the four
  evaluation apps (Amazon, Twitter, Airbnb, Slack) and their
  bug-injected counterparts
- `app/` — Flask backend that serves the constraint-builder UI and
  runs static checks on demand
- `static/js/constraint-builder.js` — overlay injected into user apps
  for click-to-author constraint authoring

## Reproducing the evaluation

The eval script runs the full constraint set across all four modified
apps and reports pass/fail against expected verdicts:

```bash
python3 eval.py
```

Outputs a per-constraint verdict table and writes `eval_results.md`.
Individual test suites for specific features (multi-hop write chains,
if/else universality, classList mutations, counterfactual constraints,
etc.) live alongside `eval.py`.

## Adding a new test app

1. Drop the app under `test-app-<name>/`.
2. Run `inject_ids` via the UI or `python -m src.mapping.inject_ids
   test-app-<name>/` to insert synthetic ids into elements that lack them.
3. Open the app in the browser with the overlay attached and author
   constraints. Save them; the tool runs the static checks and reports
   results inline.

## Regenerating the parser

If you modify `Constraint.g4`:

```bash
antlr4 -Dlanguage=Python3 -visitor Constraint.g4
```

This regenerates `ConstraintParser.py`, `ConstraintListener.py`, and
`ConstraintVisitor.py`.
