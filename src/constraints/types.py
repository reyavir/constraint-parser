"""
Constraint type enumeration.

Each variant maps to a distinct verification strategy:

    PROBABILISTIC  — P(w(ej) | A(ei)) = p
                     Verified by counting how often ej is written across traces
                     where A(ei) fires.

    VALUE          — P(w(ej, expr) | A(ei)) = p where expr is a constant /
                     external (LiteralExpr, LenExpr, StatusExpr).
                     Runtime-only: verify the trace value matches expr.

    VALUE_WITH_DATAFLOW
                   — P(w(ej, expr) | A(ei)) = p where expr derives from another
                     element (ReadExpr/FuncExpr/IncrementExpr/BinaryExpr).
                     Runtime + CodeQL: runtime verifies the value match, CodeQL
                     verifies a data-flow path actually exists from the source
                     element to ej (otherwise the match might be coincidental).

    COUNTERFACTUAL — P(w(ej) | ¬A(ei)) = 0
                     The condition is negated; checks that ej does NOT update
                     when the action is absent.

    API_CALL       — P(call(api) | A(ei)) = p
                     Verified by intercepting network calls in traces.

    COMPOUND       — P(w(a) ∧ w(b) | A(ei)) = p
                     Both elements must update; checked together per trace.

    EXCLUSIVE      — P(w(a) XOR w(b) | A(ei)) = p
                     Exactly one element updates; checked per trace.

    ORDER          — P(seq(w(a)) < seq(w(b)) | A(ei)) = p
                     Ordering of writes; verified via sequenced trace log.

    GUARD          — P(<guard-expr> | A(ei)) = p
                     The event side is a Guard expression, i.e. an
                     assertion about a value (comparison, length, etc.).
                     Examples: P(r(cart) = 0 | A(clearBtn)) = 1,
                               P(len(r(a)) = len(r(b)) | A(ei)) = 1.
                     Verified at runtime by reading the relevant values
                     after the action fires.

                     NOTE: this refers to a guard appearing as the *event*
                     (left side of `|`). Action nodes can also carry a
                     `guard` field on the *condition* side (Row 5,
                     guarded_write). They live at different AST positions.

    STATIC         — static:check_type(element)
                     No runtime traces; resolved by CodeQL queries.
"""

from enum import Enum, auto


class ConstraintType(Enum):
    PROBABILISTIC       = auto()
    VALUE               = auto()
    VALUE_WITH_DATAFLOW = auto()
    COUNTERFACTUAL      = auto()
    API_CALL            = auto()
    COMPOUND            = auto()
    EXCLUSIVE           = auto()
    PERSIST             = auto()
