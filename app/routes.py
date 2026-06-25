import json
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify, abort, send_file

from src.parser.lexer import LexerError
from src.parser.parser import parse, parse_with_steps, ParseError, SemanticError
from src.constraints.classifier import classify
from src.constraints.types import ConstraintType
from src.constraints.semantic import analyze as analyze_semantics
from src.constraints.explain import classification_trace, dispatch_plan
from src.mapping.pipeline import MAPPING_FILE
from src.mapping.scan_ids import scan_element_ids
from src.instrumenter import inject_ids, repo_status, inject_script, rewrite_absolute_paths
from src.verifier import check_probabilistic
from src.tracer import generate_traces_for_constraint
from src.static_checks import stage1_check
from .serializer import serialize_tokens, serialize_ast, serialize_constraint_type
from .demo_backend import set_app_dir, get_app_dir

# Names of ConstraintType variants whose checker is wired end-to-end.
_IMPLEMENTED: set[str] = {"PROBABILISTIC"}

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
            "success":             True,
            "tokens":              serialize_tokens(tokens),
            "parse_tree":          parse_tree,
            "ast":                 serialize_ast(ast),
            "type":                type_payload,
            "semantics":           semantics,
            "verifiable":          verifiable,
            "classification_trace": classification_trace(ast),
            "dispatch_plan":       dispatch_plan(ast),
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
        "elements":     len(mapping.get("elements") or {}),
        "apis":         len(mapping.get("apis") or {}),
        "storage":      len(mapping.get("storage") or {}),
        "path":         str(MAPPING_FILE),
    })


@bp.post("/verify/stage1")
def verify_stage1():
    """Run Stage 1 static checks against the dict AST for *constraint*."""
    data    = request.get_json(silent=True) or {}
    source  = (data.get("constraint") or "").strip()
    db_path = (data.get("db_path") or "./codeql-db").strip()

    if not source:
        return jsonify({"success": False, "error": "No constraint provided."}), 400

    try:
        ast    = parse(source)
        result = stage1_check(ast, db_path=db_path)
        return jsonify({"success": True, **result})
    except (ParseError, SemanticError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"success": False, "error": f"Unexpected: {exc}"}), 500


@bp.post("/codeql/rebuild")
def codeql_rebuild():
    """Shell out to `codeql database create --overwrite` to refresh the DB."""
    import subprocess

    data       = request.get_json(silent=True) or {}
    source_dir = (data.get("source_dir") or "").strip()
    db_path    = (data.get("db_path")    or "./codeql-db").strip()
    if not source_dir:
        return jsonify({"success": False, "error": "No source path provided."}), 400
    if not Path(source_dir).is_dir():
        return jsonify({"success": False, "error": f"Source not found: {source_dir}"}), 400

    cmd = [
        "codeql", "database", "create", db_path,
        "--language=javascript",
        f"--source-root={source_dir}",
        "--overwrite",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        last_err = (proc.stderr.strip().splitlines() or ["codeql CLI failed."])[-1]
        return jsonify({"success": False, "error": last_err, "stderr": proc.stderr}), 500

    # Build succeeded — make this the app /run/ serves so the iframe /
    # preview and the freshly-built DB stay in sync.
    try:
        active = set_app_dir(source_dir)
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({
        "success": True,
        "db_path": db_path,
        "app_dir": str(active),
    })


@bp.post("/verify")
def verify_constraint():
    """
    Stage 2 — runtime verification. Generates *n_traces* Playwright runs
    against the user's app, then evaluates the constraint against the
    collected rollups. Only PROBABILISTIC is wired so far.

    Expected JSON body:
        {
            "constraint": "P(w(cart-count) | A(add-to-cart-btn)) = 1",
            "url":        "http://localhost:8080",
            "n_traces":   30,                       # optional, default 30
            "random_suffix": 3,                     # optional, default 3
            "headless":   true,                     # optional, default true
            "mocks":      {"/api/cart": {           # optional
                              "status": 200,
                              "body":   {"totalItems": 1}
                          }},
            "seed":       null                      # optional
        }
    """
    data        = request.get_json(silent=True) or {}
    source      = (data.get("constraint") or "").strip()
    url         = (data.get("url") or "").strip()
    n_traces    = int(data.get("n_traces") or 30)
    random_sfx  = int(data.get("random_suffix") if data.get("random_suffix") is not None else 3)
    headless    = bool(data.get("headless", True))
    mocks       = data.get("mocks") or None
    seed        = data.get("seed")

    if not source:
        return jsonify({"success": False, "error": "No constraint provided."}), 400
    if not url:
        return jsonify({"success": False, "error": "Missing app URL. Start your app and pass `url`."}), 400

    try:
        ast   = parse(source)
        ctype = classify(ast)
    except (LexerError, ParseError, SemanticError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 422

    if ctype != ConstraintType.PROBABILISTIC:
        return jsonify({
            "success": False,
            "error":   f"Runtime verifier for {ctype.name} is not wired yet — only PROBABILISTIC is implemented.",
            "type":    ctype.name,
        }), 400

    if not MAPPING_FILE.exists():
        return jsonify({
            "success": False,
            "error":   "No element mapping found. Run `Scan IDs` first.",
        }), 400

    try:
        mapping = json.loads(MAPPING_FILE.read_text())
    except Exception as exc:
        return jsonify({"success": False, "error": f"Could not read mapping: {exc}"}), 500

    try:
        traces = generate_traces_for_constraint(
            url=url,
            ast=ast,
            mapping=mapping,
            n=n_traces,
            random_suffix=random_sfx,
            mock_responses=mocks,
            headless=headless,
            seed=seed,
        )
    except Exception as exc:
        return jsonify({"success": False, "error": f"Trace generation failed: {exc}"}), 500

    result = check_probabilistic(ast, traces)
    # Return only a sample of the raw traces so the response stays small;
    # everything the verifier needed is in the result summary already.
    return jsonify({
        "success":       True,
        "type":          ctype.name,
        **result,
        "traces_total":  len(traces),
        "traces_sample": traces[:3],
    })


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
        {
            "id":       k,
            "label":    (v or {}).get("label", k),
            "endpoint": (v or {}).get("endpoint"),
            "method":   (v or {}).get("method"),
            "file":     (v or {}).get("file"),
            "line":     (v or {}).get("line"),
        }
        for k, v in (mapping.get("apis") or {}).items()
    ]
    storage = [
        {
            "id":   k,
            "area": (v or {}).get("area"),
            "key":  (v or {}).get("key"),
            "ops":  (v or {}).get("ops", []),
            "file": (v or {}).get("file"),
            "line": (v or {}).get("line"),
        }
        for k, v in (mapping.get("storage") or {}).items()
    ]
    return jsonify({
        "available":      True,
        "elements":       elements,
        "apis":           apis,
        "storage":        storage,
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
