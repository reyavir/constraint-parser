import json
import threading

from flask import Blueprint, render_template, request, jsonify

from src.parser.lexer import LexerError
from src.parser.parser import parse, parse_with_steps, ParseError, SemanticError
from src.constraints.classifier import classify
from src.constraints.semantic import analyze as analyze_semantics
from src.mapping.codeql_runner import collect_raw_elements
from src.mapping.generator import generate_draft_mapping
from src.mapping.pipeline import MAPPING_FILE
from src.verifier import verify as run_verify
from .serializer import serialize_tokens, serialize_ast, serialize_constraint_type

# Names of ConstraintType variants whose checker is wired end-to-end. Populate
# as verifiers ship (currently empty — every branch in src/verifier.py is a
# stub that raises NotImplementedError).
_IMPLEMENTED: set[str] = set()

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
