"""
Converts lexer tokens and parser AST nodes into plain JSON-serializable dicts
for the API response.
"""

from __future__ import annotations
from typing import Any

from src.parser.lexer import Token, TokenKind
from src.parser.ast_nodes import (
    ProbabilisticConstraint, StaticConstraint,
    WriteEvent, CompoundWriteEvent, SeqOrderEvent, LenMatchEvent, ApiCallEvent,
    ActionCondition, ApiErrorCondition, ApiStatusCondition, CompoundCondition,
    ReadExpr, FuncExpr, ArithExpr, LenExpr, StatusExpr,
    NumberLiteral, StringLiteral, NullLiteral,
    ElementRef, Guard, RangeExpr,
)
from src.constraints.types import ConstraintType


# ---------------------------------------------------------------------------
# Token serialization
# ---------------------------------------------------------------------------

_KEYWORD_KINDS = {
    TokenKind.P, TokenKind.A, TokenKind.W, TokenKind.R, TokenKind.F,
    TokenKind.CALL, TokenKind.LEN, TokenKind.STATUS, TokenKind.XOR,
    TokenKind.NULL, TokenKind.NO_LITERAL, TokenKind.NO_HIDDEN_PARAM,
    TokenKind.HIDDEN_ERRORS, TokenKind.D, TokenKind.API,
}
_OPERATOR_KINDS = {
    TokenKind.NOT, TokenKind.AND, TokenKind.PLUS, TokenKind.MINUS,
    TokenKind.LT, TokenKind.GT, TokenKind.LTE, TokenKind.GTE, TokenKind.NEQ,
    TokenKind.PIPE, TokenKind.LAST,
}
_PUNCTUATION_KINDS = {
    TokenKind.LPAREN, TokenKind.RPAREN, TokenKind.COMMA, TokenKind.EQUALS,
    TokenKind.LBRACKET, TokenKind.RBRACKET,
}


def _token_category(kind: TokenKind) -> str:
    if kind in _KEYWORD_KINDS:    return "keyword"
    if kind == TokenKind.IDENTIFIER: return "identifier"
    if kind == TokenKind.NUMBER:  return "number"
    if kind == TokenKind.STRING:  return "string"
    if kind in _OPERATOR_KINDS:   return "operator"
    if kind in _PUNCTUATION_KINDS: return "punctuation"
    return "other"


def serialize_tokens(tokens: list[Token]) -> list[dict]:
    return [
        {
            "kind": tok.kind.name,
            "value": tok.value,
            "pos": tok.pos,
            "category": _token_category(tok.kind),
        }
        for tok in tokens
        if tok.kind != TokenKind.EOF
    ]


# ---------------------------------------------------------------------------
# AST serialization — recursive, mirrors the node hierarchy
# ---------------------------------------------------------------------------

def serialize_ast(node: Any) -> dict | None:
    if node is None:
        return None

    # ── Top-level constraints ──────────────────────────────────────────────

    if isinstance(node, ProbabilisticConstraint):
        return {
            "node_type": "ProbabilisticConstraint",
            "event": serialize_ast(node.event),
            "condition": serialize_ast(node.condition),
            "probability_op": node.probability_op,
            "probability": node.probability,
        }

    if isinstance(node, StaticConstraint):
        return {
            "node_type": "StaticConstraint",
            "check_type": node.check_type,
            "target": serialize_ast(node.target),
        }

    # ── Events ────────────────────────────────────────────────────────────

    if isinstance(node, WriteEvent):
        return {
            "node_type": "WriteEvent",
            "element": serialize_ast(node.element),
            "value_expr": serialize_ast(node.value_expr),
        }

    if isinstance(node, CompoundWriteEvent):
        return {
            "node_type": "CompoundWriteEvent",
            "op": node.op,
            "left": serialize_ast(node.left),
            "right": serialize_ast(node.right),
        }

    if isinstance(node, SeqOrderEvent):
        return {
            "node_type": "SeqOrderEvent",
            "first": serialize_ast(node.first),
            "second": serialize_ast(node.second),
        }

    if isinstance(node, LenMatchEvent):
        return {
            "node_type": "LenMatchEvent",
            "left": serialize_ast(node.left),
            "right": serialize_ast(node.right),
        }

    if isinstance(node, ApiCallEvent):
        return {
            "node_type": "ApiCallEvent",
            "api_ref": node.api_ref,
            "params": serialize_ast(node.params),
        }

    # ── Conditions ────────────────────────────────────────────────────────

    if isinstance(node, ActionCondition):
        return {
            "node_type": "ActionCondition",
            "element": serialize_ast(node.element),
            "negated": node.negated,
            "guard": serialize_ast(node.guard),
        }

    if isinstance(node, CompoundCondition):
        return {
            "node_type": "CompoundCondition",
            "op": node.op,
            "left": serialize_ast(node.left),
            "right": serialize_ast(node.right),
        }

    if isinstance(node, ApiErrorCondition):
        return {
            "node_type": "ApiErrorCondition",
            "api_ref": node.api_ref,
        }

    if isinstance(node, ApiStatusCondition):
        return {
            "node_type": "ApiStatusCondition",
            "api_ref": node.api_ref,
            "op": node.op,
            "status_code": node.status_code,
        }

    if isinstance(node, Guard):
        return {
            "node_type": "Guard",
            "left": serialize_ast(node.left),
            "op": node.op,
            "right": serialize_ast(node.right),
        }

    # ── Value expressions ─────────────────────────────────────────────────

    if isinstance(node, ReadExpr):
        return {
            "node_type": "ReadExpr",
            "source": serialize_ast(node.source),
            "last": node.last,
        }

    if isinstance(node, LenExpr):
        return {
            "node_type": "LenExpr",
            "arg": serialize_ast(node.arg),
        }

    if isinstance(node, StatusExpr):
        return {
            "node_type": "StatusExpr",
            "api_ref": node.api_ref,
        }

    if isinstance(node, FuncExpr):
        return {
            "node_type": "FuncExpr",
            "arg": serialize_ast(node.arg),
        }

    if isinstance(node, ArithExpr):
        return {
            "node_type": "ArithExpr",
            "left": serialize_ast(node.left),
            "op": node.op,
            "right": serialize_ast(node.right),
        }

    if isinstance(node, NumberLiteral):
        return {"node_type": "NumberLiteral", "value": node.value}

    if isinstance(node, StringLiteral):
        return {"node_type": "StringLiteral", "value": node.value}

    if isinstance(node, NullLiteral):
        return {"node_type": "NullLiteral"}

    if isinstance(node, ElementRef):
        return {"node_type": "ElementRef", "name": node.name}

    if isinstance(node, RangeExpr):
        return {
            "node_type": "RangeExpr",
            "low": node.low,
            "high": node.high,
            "distribution": node.distribution,
        }

    return {"node_type": "Unknown", "repr": repr(node)}


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
            "Like Probabilistic, but also capture the actual value written to ej in each "
            "trace and verify it matches the value expression (e.g. r(ei) + 1)."
        ),
        "checker": "check_value(params, traces)",
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
