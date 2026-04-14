from flask import Blueprint, render_template, request, jsonify

from src.parser.lexer import tokenize, LexerError
from src.parser.parser import parse, ParseError
from src.constraints.classifier import classify
from .serializer import serialize_tokens, serialize_ast, serialize_constraint_type

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
        tokens = tokenize(source)
        ast    = parse(source)
        ctype  = classify(ast)

        return jsonify({
            "success": True,
            "tokens":  serialize_tokens(tokens),
            "ast":     serialize_ast(ast),
            "type":    serialize_constraint_type(ctype),
        })

    except LexerError as exc:
        return jsonify({"success": False, "error": f"Lexer error: {exc}"}), 422

    except ParseError as exc:
        return jsonify({"success": False, "error": f"Parse error: {exc}"}), 422

    except Exception as exc:          # unexpected — show a safe message
        return jsonify({"success": False, "error": f"Unexpected error: {exc}"}), 500
