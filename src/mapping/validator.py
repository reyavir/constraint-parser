"""
Identifier validation against the approved element mapping.

After parsing, every ElementRef and API ref in the AST must exist in
element_mapping.json. This catches typos and unknown identifiers before
verification is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..parser.ast_nodes import (
    ProbabilisticConstraint, StaticConstraint,
    WriteEvent, CompoundWriteEvent, SeqOrderEvent, LenMatchEvent,
    ApiCallEvent, ActionCondition, CompoundCondition,
    ApiErrorCondition, ApiStatusCondition,
    ReadExpr, LenExpr, FuncExpr, ArithExpr, ElementRef,
)
from .pipeline import load_mapping, MAPPING_FILE


@dataclass
class ValidationResult:
    valid: bool
    unknown_elements: list[str]
    unknown_apis: list[str]

    def to_dict(self) -> dict:
        return {
            "valid":            self.valid,
            "unknown_elements": self.unknown_elements,
            "unknown_apis":     self.unknown_apis,
        }


def validate_identifiers(ast: Any) -> ValidationResult:
    """
    Walk *ast* and check every identifier against the approved mapping.

    Returns a ValidationResult indicating which identifiers (if any) are
    not present in element_mapping.json.

    Raises FileNotFoundError if no mapping has been approved yet.
    """
    mapping          = load_mapping(MAPPING_FILE)
    known_elements   = set(mapping.get("elements", {}).keys())
    known_apis       = set(mapping.get("apis", {}).keys())

    found_elements: set[str] = set()
    found_apis:     set[str] = set()

    _collect(ast, found_elements, found_apis)

    unknown_elements = sorted(found_elements - known_elements)
    unknown_apis     = sorted(found_apis     - known_apis)

    return ValidationResult(
        valid            = not unknown_elements and not unknown_apis,
        unknown_elements = unknown_elements,
        unknown_apis     = unknown_apis,
    )


# ---------------------------------------------------------------------------
# AST walker — collects all ElementRef names and api_ref strings
# ---------------------------------------------------------------------------

def _collect(node: Any, elements: set[str], apis: set[str]) -> None:
    if node is None:
        return

    # ── Top-level constraints ─────────────────────────────────────────────

    if isinstance(node, ProbabilisticConstraint):
        _collect(node.event, elements, apis)
        _collect(node.condition, elements, apis)
        return

    if isinstance(node, StaticConstraint):
        if node.target is not None:
            _collect(node.target, elements, apis)
        return

    # ── Events ────────────────────────────────────────────────────────────

    if isinstance(node, WriteEvent):
        _collect(node.element, elements, apis)
        _collect(node.value_expr, elements, apis)
        return

    if isinstance(node, CompoundWriteEvent):
        _collect(node.left, elements, apis)
        _collect(node.right, elements, apis)
        return

    if isinstance(node, SeqOrderEvent):
        _collect(node.first, elements, apis)
        _collect(node.second, elements, apis)
        return

    if isinstance(node, LenMatchEvent):
        _collect(node.left, elements, apis)
        _collect(node.right, elements, apis)
        return

    if isinstance(node, ApiCallEvent):
        apis.add(node.api_ref)
        return

    # ── Conditions ────────────────────────────────────────────────────────

    if isinstance(node, ActionCondition):
        _collect(node.element, elements, apis)
        return

    if isinstance(node, CompoundCondition):
        _collect(node.left, elements, apis)
        _collect(node.right, elements, apis)
        return

    if isinstance(node, ApiErrorCondition):
        apis.add(node.api_ref)
        return

    if isinstance(node, ApiStatusCondition):
        apis.add(node.api_ref)
        return

    # ── Value expressions ─────────────────────────────────────────────────

    if isinstance(node, ReadExpr):
        _collect(node.source, elements, apis)
        return

    if isinstance(node, LenExpr):
        _collect(node.arg, elements, apis)
        return

    if isinstance(node, FuncExpr):
        _collect(node.arg, elements, apis)
        return

    if isinstance(node, ArithExpr):
        _collect(node.left, elements, apis)
        _collect(node.right, elements, apis)
        return

    # ── Leaf ──────────────────────────────────────────────────────────────

    if isinstance(node, ElementRef):
        elements.add(node.name)
        return
