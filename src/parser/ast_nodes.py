"""
AST node definitions for the constraint language.

Every node is a frozen dataclass so callers can't accidentally mutate
parsed results, and equality/hashing work out-of-the-box.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Leaf nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ElementRef:
    """Reference to a UI element by name (e.g. 'cartDisplay')."""
    name: str

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NumberLiteral:
    value: float

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class StringLiteral:
    value: str

    def __str__(self) -> str:
        return f'"{self.value}"'


@dataclass(frozen=True)
class NullLiteral:
    def __str__(self) -> str:
        return "null"


# ---------------------------------------------------------------------------
# Value expressions  (right-hand side of a write, inside guards, etc.)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReadExpr:
    """r(element) or r(api_result) — reads the current value of a source."""
    source: ElementRef  # element name or the special sentinel "api_result"
    last: bool = False  # True when the "_last" modifier is present

    def __str__(self) -> str:
        suffix = "_last" if self.last else ""
        return f"r({self.source}){suffix}"


@dataclass(frozen=True)
class LenExpr:
    """len(r(element|api_result))"""
    arg: ReadExpr

    def __str__(self) -> str:
        return f"len({self.arg})"


@dataclass(frozen=True)
class StatusExpr:
    """status(api)"""
    api_ref: str = "api"

    def __str__(self) -> str:
        return f"status({self.api_ref})"


@dataclass(frozen=True)
class FuncExpr:
    """f(value_expr) — apply a generic function to an expression."""
    arg: Any  # value_expr node

    def __str__(self) -> str:
        return f"f({self.arg})"


@dataclass(frozen=True)
class ArithExpr:
    """Binary arithmetic: left op right."""
    left: Any   # value_expr node
    op: str     # '+' | '-' | '*' | '/'
    right: Any  # value_expr node

    def __str__(self) -> str:
        return f"({self.left} {self.op} {self.right})"


# ---------------------------------------------------------------------------
# Events (left side of the | in P(...|...))
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WriteEvent:
    """w(element) or w(element, value_expr)."""
    element: ElementRef
    value_expr: Optional[Any] = None  # None → just check that a write happened

    def __str__(self) -> str:
        if self.value_expr is not None:
            return f"w({self.element}, {self.value_expr})"
        return f"w({self.element})"


@dataclass(frozen=True)
class CompoundWriteEvent:
    """write_event ∧ write_event  (op='AND')  or  write_event XOR write_event  (op='XOR')."""
    op: str          # 'AND' | 'XOR'
    left: Any
    right: Any

    def __str__(self) -> str:
        sym = "∧" if self.op == "AND" else "XOR"
        return f"{self.left} {sym} {self.right}"


@dataclass(frozen=True)
class SeqOrderEvent:
    """seq(write_event) < seq(write_event) — ordering constraint."""
    first: WriteEvent
    second: WriteEvent

    def __str__(self) -> str:
        return f"seq({self.first}) < seq({self.second})"


@dataclass(frozen=True)
class LenMatchEvent:
    """len(read_expr) = len(read_expr) — length equality constraint."""
    left: ReadExpr
    right: ReadExpr

    def __str__(self) -> str:
        return f"len({self.left}) = len({self.right})"


@dataclass(frozen=True)
class ApiCallEvent:
    """call(api_ref) or call(api_ref, value_expr)."""
    api_ref: str
    params: Optional[Any] = None  # value_expr for the parameters

    def __str__(self) -> str:
        if self.params is not None:
            return f"call({self.api_ref}, {self.params})"
        return f"call({self.api_ref})"


# ---------------------------------------------------------------------------
# Guard (optional refinement on a condition)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Guard:
    """Predicate constraint used by event/condition atoms."""
    left: Any
    op: str
    right: Any

    def __str__(self) -> str:
        return f"{self.left} {self.op} {self.right}"


@dataclass(frozen=True)
class RangeExpr:
    """[low, high] inclusive range or D distribution sentinel."""
    low: Optional[float] = None
    high: Optional[float] = None
    distribution: Optional[str] = None

    def __str__(self) -> str:
        if self.distribution is not None:
            return self.distribution
        return f"[{self.low}, {self.high}]"


# ---------------------------------------------------------------------------
# Conditions (right side of the | in P(...|...))
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionCondition:
    """A(element) or ¬A(element), with an optional guard."""
    element: ElementRef
    negated: bool = False
    guard: Optional[Guard] = None

    def __str__(self) -> str:
        prefix = "¬" if self.negated else ""
        base = f"{prefix}A({self.element})"
        if self.guard is not None:
            return f"{base}, {self.guard}"
        return base


@dataclass(frozen=True)
class CompoundCondition:
    """condition_atom ∧ condition_atom"""
    op: str
    left: Any
    right: Any

    def __str__(self) -> str:
        return f"{self.left} {self.op} {self.right}"


@dataclass(frozen=True)
class ApiErrorCondition:
    """error(api_ref) — the API call returned an error."""
    api_ref: str

    def __str__(self) -> str:
        return f"error({self.api_ref})"


@dataclass(frozen=True)
class ApiStatusCondition:
    """status(api_ref) op NUMBER — the API returned a specific HTTP status."""
    api_ref: str
    op: str    # '<' | '>' | '<=' | '>=' | '==' | '!='
    status_code: float

    def __str__(self) -> str:
        return f"status({self.api_ref}) {self.op} {int(self.status_code)}"


# ---------------------------------------------------------------------------
# Top-level constraints
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProbabilisticConstraint:
    """P(event | condition) = probability"""
    event: Any              # any Event node
    condition: Any          # any Condition node
    probability_op: str
    probability: float
    raw: str = field(default="", compare=False)

    def __str__(self) -> str:
        return f"P({self.event} | {self.condition}) {self.probability_op} {self.probability}"


@dataclass(frozen=True)
class StaticConstraint:
    """static:check_type(target) — resolved via CodeQL, no runtime traces needed."""
    check_type: str
    target: Optional[ElementRef] = None
    raw: str = field(default="", compare=False)

    def __str__(self) -> str:
        if self.target is None:
            return f"{self.check_type}()"
        return f"{self.check_type}({self.target})"
