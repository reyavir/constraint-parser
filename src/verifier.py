"""
Verification dispatcher.

Takes a parsed constraint AST node and routes it to the appropriate
verification strategy based on its ConstraintType.

Usage
-----
    from src.parser import parse
    from src.verifier import verify

    result = verify(parse("P(w(cartDisplay) | A(addBtn)) = 1"), traces=traces)
"""

from __future__ import annotations

from typing import Any

from .constraints.classifier import classify
from .constraints.types import ConstraintType
from .parser.ast_nodes import StaticConstraint


# ---------------------------------------------------------------------------
# CodeQL query stubs — fill in real query strings when ready
# ---------------------------------------------------------------------------

NO_LITERAL_QUERY    = ""  # TODO
NO_HIDDEN_PARAM_QUERY = ""  # TODO
HIDDEN_ERROR_QUERY  = ""  # TODO


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def verify(parsed: Any, traces: Any = None, network_log: Any = None) -> Any:
    """
    Dispatch *parsed* to the correct verification function.

    Parameters
    ----------
    parsed:
        A top-level AST node returned by ``parse()``.
    traces:
        Runtime trace data required by most dynamic checks.
    network_log:
        Network intercept log required only for API_CALL constraints.
    """
    ctype = classify(parsed)

    match ctype:
        case ConstraintType.PROBABILISTIC:
            return check_probabilistic(parsed, traces)
        case ConstraintType.VALUE:
            return check_value(parsed, traces)
        case ConstraintType.COUNTERFACTUAL:
            return check_counterfactual(parsed, traces)
        case ConstraintType.API_CALL:
            return check_api_call(parsed, traces, network_log)
        case ConstraintType.COMPOUND:
            return check_compound(parsed, traces)
        case ConstraintType.EXCLUSIVE:
            return check_exclusive(parsed, traces)
        case ConstraintType.ORDER:
            return check_order(parsed, traces)
        case ConstraintType.LENGTH_MATCH:
            return check_length(parsed, traces)
        case ConstraintType.STATIC:
            return _dispatch_static(parsed)


def _dispatch_static(parsed: StaticConstraint) -> Any:
    """Further dispatch STATIC constraints by their check_type."""
    match parsed.check_type:
        case "no_literal":
            return run_codeql(NO_LITERAL_QUERY, parsed)
        case "no_hidden_param":
            return run_codeql(NO_HIDDEN_PARAM_QUERY, parsed)
        case "hidden_error":
            return run_codeql(HIDDEN_ERROR_QUERY, parsed)
        case _:
            raise ValueError(f"Unknown static check_type: {parsed.check_type!r}")


# ---------------------------------------------------------------------------
# Verification stubs — implement each when ready
# ---------------------------------------------------------------------------

def check_probabilistic(parsed: Any, traces: Any) -> Any:
    pass


def check_value(parsed: Any, traces: Any) -> Any:
    pass


def check_counterfactual(parsed: Any, traces: Any) -> Any:
    pass


def check_api_call(parsed: Any, traces: Any, network_log: Any) -> Any:
    pass


def check_compound(parsed: Any, traces: Any) -> Any:
    pass


def check_exclusive(parsed: Any, traces: Any) -> Any:
    pass


def check_order(parsed: Any, traces: Any) -> Any:
    pass


def check_length(parsed: Any, traces: Any) -> Any:
    pass


def run_codeql(query: str, parsed: StaticConstraint) -> Any:
    pass
