"""
Visitor 2 — semantic analysis on the dict AST.

Walks the AST returned by `src.parser.ast_visitor.ASTBuilder` and enforces:

  1. Condition side must contain a user action A(...) or system action call(...).
  2. Event side must contain a write event w(...), system action call(...),
     compound event, or guard.
  3. Element in A(e) must exist in the mapping and be kind="action".
  4. Element in w(e) must exist in the mapping.
  5. Element in r(e) (and len/increment over it) must exist in the mapping.
  6. Probability must lie in [0, 1].
  7. API in call(api) (and status(api)) must exist in the mapping.
  8. The only action allowed on the event side is a system action — no A(...).

`analyze()` collects every violation rather than failing fast so the UI can
surface them all in one pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..mapping.pipeline import load_mapping, MAPPING_FILE


# Element identifiers that are language sentinels, not real UI elements.
_BUILTIN_ELEMENT_NAMES = {"api_result"}


@dataclass
class SemanticIssue:
    code: str        # short stable code, e.g. "E001"
    message: str     # human-readable detail

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


@dataclass
class SemanticAnalysisResult:
    valid: bool
    issues: list[SemanticIssue]

    def to_dict(self) -> dict:
        return {
            "valid":  self.valid,
            "issues": [i.to_dict() for i in self.issues],
        }


def analyze(ast: dict, mapping: dict | None = None) -> SemanticAnalysisResult:
    """Run every semantic check and return the collected issues."""
    issues: list[SemanticIssue] = []

    # Load the approved mapping if the caller didn't pre-supply one. Identifier
    # checks are silently skipped if no mapping has been approved yet.
    if mapping is None and MAPPING_FILE.exists():
        try:
            mapping = load_mapping(MAPPING_FILE)
        except Exception:
            mapping = None

    if not isinstance(ast, dict) or ast.get("type") != "Probabilistic":
        issues.append(SemanticIssue(
            "E000", "Top-level constraint must be a probabilistic constraint."))
        return SemanticAnalysisResult(valid=False, issues=issues)

    event     = ast.get("event")
    condition = ast.get("condition")

    _check_probability(ast, issues)
    _check_condition_side(condition, issues)
    _check_event_side(event, issues)

    if mapping is not None:
        _check_identifiers(ast, mapping, issues)

    return SemanticAnalysisResult(valid=(not issues), issues=issues)


# ---------------------------------------------------------------------------
# Structural rules (1, 2, 6, 8)
# ---------------------------------------------------------------------------

def _check_probability(ast: dict, issues: list[SemanticIssue]) -> None:
    p = ast.get("probability")
    if not isinstance(p, (int, float)) or isinstance(p, bool):
        issues.append(SemanticIssue(
            "E006", f"Probability must be a number, got {p!r}."))
        return
    if p < 0 or p > 1:
        issues.append(SemanticIssue(
            "E006", f"Probability {p} must be in [0, 1]."))


def _check_condition_side(condition: Any, issues: list[SemanticIssue]) -> None:
    """Rule 1."""
    if not _contains_any_type(condition, {"Action", "CallEvent"}):
        issues.append(SemanticIssue(
            "E001",
            "Right side of '|' (condition) must contain a user action "
            "A(...) or a system action call(...)."))


def _check_event_side(event: Any, issues: list[SemanticIssue]) -> None:
    """Rules 2 and 8."""
    allowed = {"WriteEvent", "CallEvent", "CompoundEvent", "Guard"}
    if not _contains_any_type(event, allowed):
        issues.append(SemanticIssue(
            "E002",
            "Left side of '|' (event) must contain a write event w(...), "
            "a system action call(...), a compound event, or a guard."))
    if _contains_any_type(event, {"Action"}):
        issues.append(SemanticIssue(
            "E008",
            "Left side of '|' cannot contain a user action A(...) — "
            "only system actions call(...) are allowed there."))


def _contains_any_type(node: Any, type_set: set[str]) -> bool:
    """True if any dict in the subtree has `type` in *type_set*."""
    if isinstance(node, dict):
        if node.get("type") in type_set:
            return True
        return any(_contains_any_type(v, type_set) for v in node.values())
    if isinstance(node, list):
        return any(_contains_any_type(item, type_set) for item in node)
    return False


# ---------------------------------------------------------------------------
# Identifier rules (3, 4, 5, 7)
# ---------------------------------------------------------------------------

def _check_identifiers(ast: dict, mapping: dict, issues: list[SemanticIssue]) -> None:
    elements: dict = mapping.get("elements", {})
    apis: dict     = mapping.get("apis", {})

    for node in _walk_dicts(ast):
        ntype = node.get("type")

        if ntype == "Action":
            _check_action_element(node, elements, issues)

        elif ntype == "WriteEvent":
            name = node.get("element")
            if not isinstance(name, str):
                continue
            if name in _BUILTIN_ELEMENT_NAMES or name not in elements:
                issues.append(SemanticIssue(
                    "E004",
                    f"Element '{name}' in w({name}) is not in the mapping."))

        elif ntype in ("ReadExpr", "LenExpr", "IncrementExpr"):
            name = node.get("element")
            if not isinstance(name, str):
                continue
            if name in _BUILTIN_ELEMENT_NAMES:
                continue  # api_result is a language sentinel, not a UI element
            if name not in elements:
                issues.append(SemanticIssue(
                    "E005",
                    f"Element '{name}' in r({name}) is not in the mapping."))

        elif ntype in ("CallEvent", "StatusExpr"):
            # API auto-discovery is not in the scan_ids pipeline yet, so we
            # only validate APIs when the user has manually populated the
            # apis section of element_mapping.json.
            if not apis:
                continue
            api_name = node.get("api")
            if isinstance(api_name, str) and api_name not in apis:
                issues.append(SemanticIssue(
                    "E007",
                    f"API '{api_name}' is not in the extracted API mapping."))


def _check_action_element(node: dict, elements: dict, issues: list[SemanticIssue]) -> None:
    """Rule 3: ei in A(ei) must exist AND have kind 'action'."""
    name = node.get("element")
    if not isinstance(name, str):
        return
    if name in _BUILTIN_ELEMENT_NAMES or name not in elements:
        issues.append(SemanticIssue(
            "E003",
            f"Element '{name}' in A({name}) is not in the mapping."))
        return
    kind = elements[name].get("kind")
    if kind != "action":
        issues.append(SemanticIssue(
            "E003",
            f"Element '{name}' in A({name}) has kind '{kind or 'unknown'}', "
            f"but A(...) requires kind 'action'."))


def _walk_dicts(node: Any) -> Iterable[dict]:
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_dicts(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_dicts(item)


__all__ = ["analyze", "SemanticIssue", "SemanticAnalysisResult"]
