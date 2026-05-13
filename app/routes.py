import json
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify, abort, send_file

from src.parser.lexer import LexerError
from src.parser.parser import parse, parse_with_steps, ParseError, SemanticError
from src.constraints.classifier import classify
from src.constraints.semantic import analyze as analyze_semantics
from src.mapping.pipeline import MAPPING_FILE
from src.mapping.scan_ids import scan_element_ids
from src.instrumenter import inject_ids, repo_status, inject_script, rewrite_absolute_paths
from src.verifier import verify as run_verify
from .serializer import serialize_tokens, serialize_ast, serialize_constraint_type

# Names of ConstraintType variants whose checker is wired end-to-end. Populate
# as verifiers ship (currently empty — every branch in src/verifier.py is a
# stub that raises NotImplementedError).
_IMPLEMENTED: set[str] = set()

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.post("/parse")
def parse_constraint():
    data = request.get_json(silent=True) or {}
    source = (data.get("constraint") or "").strip()

    if not source:
        return jsonify({"success": False, "error": "No constraint provided."}), 400

    try:
        steps = parse_with_steps(source)
        tokens     = steps["tokens"]
        parse_tree = steps["parse_tree"]
        ast        = steps["ast"]

        # Classification depends on Visitor 2; tolerate NotImplementedError until
        # the dict-AST classifier lands.
        type_payload = None
        try:
            ctype = classify(ast)
            type_payload = serialize_constraint_type(ctype)
        except NotImplementedError:
            type_payload = None

        # Visitor 2 — semantic analysis (rules 1-8, including identifier checks
        # against the approved mapping).
        semantics = analyze_semantics(ast).to_dict()

        verifiable = (type_payload is not None
                      and type_payload["name"] in _IMPLEMENTED)

        return jsonify({
            "success":    True,
            "tokens":     serialize_tokens(tokens),
            "parse_tree": parse_tree,
            "ast":        serialize_ast(ast),
            "type":       type_payload,
            "semantics":  semantics,
            "verifiable": verifiable,
        })

    except LexerError as exc:
        return jsonify({"success": False, "error": f"Lexer error: {exc}"}), 422

    except ParseError as exc:
        return jsonify({"success": False, "error": f"Parse error: {exc}"}), 422

    except SemanticError as exc:
        return jsonify({"success": False, "error": f"Semantic error: {exc}"}), 422

    except Exception as exc:          # unexpected — show a safe message
        return jsonify({"success": False, "error": f"Unexpected error: {exc}"}), 500


# ── Mapping routes ─────────────────────────────────────────────────────────

@bp.post("/mapping/scan")
def mapping_scan():
    """Walk the source dir, list every DOM id + label, write element_mapping.json."""
    data       = request.get_json(silent=True) or {}
    source_dir = (data.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"success": False, "error": "No source path provided."}), 400

    try:
        mapping = scan_element_ids(source_dir)
    except FileNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": f"Unexpected: {exc}"}), 500

    MAPPING_FILE.write_text(json.dumps(mapping, indent=2))
    return jsonify({
        "success":      True,
        "elements":     len(mapping["elements"]),
        "path":         str(MAPPING_FILE),
    })


@bp.post("/verify")
def verify_constraint():
    data       = request.get_json(silent=True) or {}
    source     = (data.get("constraint") or "").strip()
    db_path    = (data.get("db_path") or "./codeql-db").strip()

    if not source:
        return jsonify({"success": False, "error": "No constraint provided."}), 400

    try:
        ast    = parse(source)
        result = run_verify(ast, db_path=db_path)
        return jsonify({"success": True, **result})

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/mapping/raw")
def mapping_raw():
    """Full mapping file contents — used by the Element Mapping tab preview."""
    if not MAPPING_FILE.exists():
        return jsonify({"available": False})
    with open(MAPPING_FILE) as f:
        return jsonify(json.load(f))


@bp.get("/mapping/elements")
def mapping_elements():
    if not MAPPING_FILE.exists():
        return jsonify({"available": False})

    with open(MAPPING_FILE) as f:
        mapping = json.load(f)

    elements = [
        {"id": k, "label": (v or {}).get("label", k)}
        for k, v in (mapping.get("elements") or {}).items()
    ]
    apis = [
        {"id": k, "label": (v or {}).get("label", k)}
        for k, v in (mapping.get("apis") or {}).items()
    ]
    return jsonify({
        "available":      True,
        "elements":       elements,
        "apis":           apis,
        "error_handlers": mapping.get("error_handlers", []),
    })


# ── ID injection ────────────────────────────────────────────────────────────

@bp.post("/instrument/check")
def instrument_check():
    """Report whether *source_dir* exists and is a git repo so the UI can
    decide whether to show the no-git confirmation banner."""
    data = request.get_json(silent=True) or {}
    source_dir = (data.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"error": "No source path provided."}), 400
    return jsonify(repo_status(source_dir))


@bp.post("/instrument")
def instrument_source():
    data = request.get_json(silent=True) or {}
    source_dir = (data.get("source_dir") or "").strip()
    confirmed  = bool(data.get("confirmed"))
    if not source_dir:
        return jsonify({"success": False, "error": "No source path provided."}), 400

    status = repo_status(source_dir)
    if not status["exists"]:
        return jsonify({"success": False, "error": f"Not a directory: {source_dir}"}), 400

    # Confirm before rewriting files in a non-git directory.
    if not status["is_git"] and not confirmed:
        return jsonify({
            "success": False,
            "needs_confirmation": True,
            "reason": "no_git",
            "path":   status["path"],
        })

    try:
        result = inject_ids(source_dir)
        return jsonify({"success": True, **result})
    except Exception as exc:
        return jsonify({"success": False, "error": f"Unexpected: {exc}"}), 500


# ── Preview (serve user's app with overlay injected) ──────────────────────

@bp.get("/preview/<path:filename>")
def preview(filename: str):
    """Serve a file from the user's source dir, rewriting HTML on the way out."""
    source = (request.args.get("source") or "").strip()
    if not source:
        return "Missing ?source=<path> query string.", 400

    root = Path(source).expanduser().resolve()
    if not root.is_dir():
        return f"Source not found: {source}", 404

    file_path = (root / filename).resolve()
    # Path-traversal guard
    try:
        file_path.relative_to(root)
    except ValueError:
        abort(403)
    if not file_path.is_file():
        abort(404)

    if file_path.suffix.lower() in (".html", ".htm"):
        html = file_path.read_text()
        html = rewrite_absolute_paths(html, source)
        html = inject_script(html)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    return send_file(file_path)


# ── Constraints inbox (overlay → server → Visual Builder tab) ─────────────

INBOX_FILE = Path("constraints_inbox.json")


def _load_inbox() -> list[dict]:
    if not INBOX_FILE.exists():
        return []
    try:
        return json.loads(INBOX_FILE.read_text())
    except Exception:
        return []


def _save_inbox(items: list[dict]) -> None:
    INBOX_FILE.write_text(json.dumps(items, indent=2))


@bp.post("/constraints/import")
def constraints_import():
    """Overlay → here. Dedupe by `created_at` and append."""
    payload = request.get_json(silent=True) or {}
    incoming = payload.get("constraints") or []
    if not isinstance(incoming, list):
        return jsonify({"success": False, "error": "Payload must contain a list."}), 400

    existing = _load_inbox()
    seen = {c.get("created_at") for c in existing}
    added = 0
    for c in incoming:
        key = c.get("created_at")
        if key and key not in seen:
            existing.append(c)
            seen.add(key)
            added += 1
    _save_inbox(existing)
    return jsonify({"success": True, "added": added, "total": len(existing)})


@bp.get("/constraints/list")
def constraints_list():
    return jsonify({"constraints": _load_inbox()})


@bp.post("/constraints/clear")
def constraints_clear():
    _save_inbox([])
    return jsonify({"success": True})
