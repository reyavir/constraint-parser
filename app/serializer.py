"""
Convert lexer tokens and the dict AST into plain JSON-serialisable shapes
for the API response.

The AST is already a dict tree (produced by the ANTLR visitor), so it round-
trips unchanged — we just enrich each token with a category so the UI can
colourise them.
"""

from __future__ import annotations
from typing import Any

from src.parser.lexer import Token
from src.constraints.types import ConstraintType


# ---------------------------------------------------------------------------
# Token serialisation
# ---------------------------------------------------------------------------

_KEYWORD_VALUES = {
    "P(", "w(", "A(", "call(", "r(", "len(", "status(", "f(",
    "api_result", "null", "D", "true", "false",
}
_OPERATOR_VALUES = {
    "+", "-", "*", "/",
    "=", "!=", "<", ">", "<=", ">=",
    "|",
    "NOT", "!", "¬",
    "AND", "&&", "∧",
    "OR",  "||", "∨",
    "XOR",
    "in",
}
_PUNCTUATION_VALUES = {"(", ")", ",", "[", "]"}
_NUMERIC_SYMBOLS  = {"NUMBER"}
_STRING_SYMBOLS   = {"STRING"}
_IDENT_SYMBOLS    = {"IDENTIFIER"}
_KEYWORD_SYMBOLS  = {"TRUE", "FALSE", "IN"}
_OPERATOR_SYMBOLS = {"NOT", "AND", "OR", "XOR"}


def _token_category(tok: Token) -> str:
    if tok.kind in _IDENT_SYMBOLS:    return "identifier"
    if tok.kind in _NUMERIC_SYMBOLS:  return "number"
    if tok.kind in _STRING_SYMBOLS:   return "string"
    if tok.kind in _KEYWORD_SYMBOLS:  return "keyword"
    if tok.kind in _OPERATOR_SYMBOLS: return "operator"
    if tok.value in _KEYWORD_VALUES:     return "keyword"
    if tok.value in _OPERATOR_VALUES:    return "operator"
    if tok.value in _PUNCTUATION_VALUES: return "punctuation"
    return "other"


def serialize_tokens(tokens: list[Token]) -> list[dict]:
    return [
        {
            "kind":     tok.kind,
            "value":    tok.value,
            "pos":      tok.pos,
            "category": _token_category(tok),
        }
        for tok in tokens
    ]


# ---------------------------------------------------------------------------
# AST serialisation — the visitor already returns plain dicts, so this is
# just a defensive pass-through that copes with None.
# ---------------------------------------------------------------------------

def serialize_ast(node: Any) -> Any:
    return node


# ---------------------------------------------------------------------------
# Constraint type metadata
# ---------------------------------------------------------------------------

_TYPE_META: dict[ConstraintType, dict] = {
    ConstraintType.PROBABILISTIC: {
        "label": "Probabilistic",
        "color": "blue",
        "summary": "Runtime trace frequency",
        "detail": (
            "Collect ~100 traces. For each trace record whether the action A(ei) fired "
            "and whether ej was written. Compute the fraction of action-traces where ej "
            "was also written, then compare to the expected probability p."
        ),
        "checker": "check_probabilistic(params, traces)",
    },
    ConstraintType.VALUE: {
        "label": "Value",
        "color": "green",
        "summary": "Runtime value comparison",
        "detail": (
            "The written value comes from a constant or an external source "
            "(literal, len(api_result), status(api)) so runtime is enough — "
            "capture the actual value written to ej and verify it matches "
            "the value expression."
        ),
        "checker": "check_value(params, traces)",
    },
    ConstraintType.VALUE_WITH_DATAFLOW: {
        "label": "Value + Dataflow",
        "color": "indigo",
        "summary": "Runtime value + CodeQL dataflow",
        "detail": (
            "The written value derives from another UI element (r(e), f(r(e)), "
            "r(e)+1, …) so runtime alone is not enough — the values could match "
            "by coincidence. Combine: runtime traces verify the value match, "
            "AND a CodeQL dataflow query verifies that a path actually exists "
            "from the source element to ej in the source code."
        ),
        "checker": "check_value(params, traces) + run_codeql(dataflow_query, db_path)",
    },
    ConstraintType.COUNTERFACTUAL: {
        "label": "Counterfactual",
        "color": "orange",
        "summary": "Runtime trace frequency (negated action)",
        "detail": (
            "Find all traces where the action did NOT fire. Verify that ej was also not "
            "written in those traces, confirming there is no spurious update."
        ),
        "checker": "check_counterfactual(params, traces)",
    },
    ConstraintType.API_CALL: {
        "label": "API Call",
        "color": "purple",
        "summary": "Network interception",
        "detail": (
            "Intercept all outgoing network calls during each trace. When A(ei) fires, "
            "verify that the specified API call is made with the expected parameters."
        ),
        "checker": "check_api_call(params, traces, network_log)",
    },
    ConstraintType.COMPOUND: {
        "label": "Compound",
        "color": "teal",
        "summary": "Multi-node runtime trace",
        "detail": (
            "In each trace where the action fires, verify that BOTH write events occur — "
            "both ej1 and ej2 must be written."
        ),
        "checker": "check_probabilistic(params, traces)  # evaluated for both nodes",
    },
    ConstraintType.EXCLUSIVE: {
        "label": "Exclusive",
        "color": "pink",
        "summary": "Multi-node runtime trace (XOR)",
        "detail": (
            "In each trace where the action fires, verify that EXACTLY ONE of the two "
            "write events occurs — not both, and not neither."
        ),
        "checker": "check_probabilistic(params, traces)  # XOR evaluated per trace",
    },
    ConstraintType.ORDER: {
        "label": "Order",
        "color": "indigo",
        "summary": "Sequenced trace log",
        "detail": (
            "Each write is logged with a global sequence number. In traces where both "
            "writes occur, verify seq(first_write) < seq(second_write)."
        ),
        "checker": "check_order(parsed, traces)",
    },
    ConstraintType.LENGTH_MATCH: {
        "label": "Length Match",
        "color": "cyan",
        "summary": "Runtime length comparison",
        "detail": (
            "Capture the length (e.g. array length) of both sources at runtime and "
            "verify they are equal in traces where the action fires."
        ),
        "checker": "check_value(params, traces)  # compares .length properties",
    },
    ConstraintType.STATIC: {
        "label": "Static",
        "color": "gray",
        "summary": "CodeQL static analysis",
        "detail": (
            "No runtime traces required. Run a CodeQL query over the codebase to check "
            "this structural property (e.g. no hardcoded literals, errors surfaced to UI)."
        ),
        "checker": "check_static(parsed, codeql_results)",
    },
}


def serialize_constraint_type(ctype: ConstraintType) -> dict:
    return {"name": ctype.name, **_TYPE_META[ctype]}
