import json
import threading

from flask import Blueprint, render_template, request, jsonify

from src.parser.lexer import tokenize, LexerError
from src.parser.parser import parse, ParseError
from src.constraints.classifier import classify
from src.mapping.codeql_runner import collect_raw_elements
from src.mapping.generator import generate_draft_mapping
from src.mapping.pipeline import MAPPING_FILE
from src.mapping.validator import validate_identifiers
from .serializer import serialize_tokens, serialize_ast, serialize_constraint_type

bp = Blueprint("main", __name__)

# Simple in-memory job state — only one mapping scan runs at a time
_job: dict = {"status": "idle", "log": [], "result": None, "error": None}


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
        tokens = tokenize(source)
        ast    = parse(source)
        ctype  = classify(ast)

        # Identifier validation — skipped silently if no mapping exists yet
        validation = None
        if MAPPING_FILE.exists():
            validation = validate_identifiers(ast).to_dict()

        return jsonify({
            "success":    True,
            "tokens":     serialize_tokens(tokens),
            "ast":        serialize_ast(ast),
            "type":       serialize_constraint_type(ctype),
            "validation": validation,
        })

    except LexerError as exc:
        return jsonify({"success": False, "error": f"Lexer error: {exc}"}), 422

    except ParseError as exc:
        return jsonify({"success": False, "error": f"Parse error: {exc}"}), 422

    except Exception as exc:          # unexpected — show a safe message
        return jsonify({"success": False, "error": f"Unexpected error: {exc}"}), 500


# ── Mapping routes ─────────────────────────────────────────────────────────

@bp.post("/mapping/generate")
def mapping_generate():
    global _job
    data    = request.get_json(silent=True) or {}
    db_path = (data.get("db_path") or "./codeql-db").strip()

    if _job["status"] == "running":
        return jsonify({"error": "A scan is already running."}), 409

    _job = {"status": "running", "log": [], "result": None, "error": None}

    def run():
        try:
            _job["log"].append("Step 1: scanning codebase with CodeQL…")
            raw = collect_raw_elements(db_path)
            _job["log"].append(
                f"Found {len(raw['actions'])} action elements, "
                f"{len(raw['displays'])} display elements, "
                f"{len(raw['apis'])} API call sites, "
                f"{len(raw['errors'])} error handlers."
            )
            _job["log"].append("Step 2: generating draft mapping with LLM…")
            draft = generate_draft_mapping(raw)
            _job["result"] = draft
            _job["status"] = "done"
            _job["log"].append("Done — review the mapping below.")
        except Exception as exc:
            _job["status"] = "error"
            _job["error"]  = str(exc)
            _job["log"].append(f"Error: {exc}")

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"started": True})


@bp.get("/mapping/status")
def mapping_status():
    return jsonify({
        "status": _job["status"],
        "log":    _job["log"],
        "result": _job["result"],
        "error":  _job["error"],
    })


@bp.post("/mapping/approve")
def mapping_approve():
    data    = request.get_json(silent=True) or {}
    mapping = data.get("mapping")

    if not mapping:
        return jsonify({"error": "No mapping provided."}), 400

    with open(MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

    return jsonify({"saved": True, "path": str(MAPPING_FILE)})


@bp.get("/mapping/elements")
def mapping_elements():
    if not MAPPING_FILE.exists():
        return jsonify({"available": False})

    with open(MAPPING_FILE) as f:
        mapping = json.load(f)

    return jsonify({
        "available": True,
        "elements":       list(mapping.get("elements", {}).keys()),
        "apis":           list(mapping.get("apis", {}).keys()),
        "error_handlers": mapping.get("error_handlers", []),
    })
