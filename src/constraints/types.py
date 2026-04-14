"""
Constraint type enumeration.

Each variant maps to a distinct verification strategy:

    PROBABILISTIC  — P(w(ej) | A(ei)) = p
                     Verified by counting how often ej is written across traces
                     where A(ei) fires.

    VALUE          — P(w(ej, expr) | A(ei)) = p
                     Like PROBABILISTIC but also checks the written value matches
                     the expression.

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

    LENGTH_MATCH   — P(len(r(a)) = len(r(b)) | A(ei)) = p
                     Runtime length comparison between two sources.

    STATIC         — static:check_type(element)
                     No runtime traces; resolved by CodeQL queries.
"""

from enum import Enum, auto


class ConstraintType(Enum):
    PROBABILISTIC  = auto()
    VALUE          = auto()
    COUNTERFACTUAL = auto()
    API_CALL       = auto()
    COMPOUND       = auto()
    EXCLUSIVE      = auto()
    ORDER          = auto()
    LENGTH_MATCH   = auto()
    STATIC         = auto()
