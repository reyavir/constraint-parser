"""
Visitor 1 — walk the ANTLR parse tree and build a dict-shaped AST.

The output dictionary structure is documented in `ast_examples.py`. Every
significant grammar node has a matching `visit*` method here; non-significant
nodes (e.g. plain pass-through rules) just delegate to their single child.

Required AST fields are validated at construction time: if a field that is
documented as required ends up None, `SemanticError` is raised so a malformed
tree never reaches downstream consumers.
"""

from __future__ import annotations

from typing import Any

from ConstraintParser import ConstraintParser
from ConstraintVisitor import ConstraintVisitor


class SemanticError(Exception):
    """Raised when the parse tree violates the AST shape contract."""


# Fields that must always be non-None for a given node type. Checked at the
# end of each visit to catch malformed trees early.
_REQUIRED: dict[str, tuple[str, ...]] = {
    "Probabilistic":  ("event", "condition", "probability", "prob_operator"),
    "WriteEvent":     ("element",),
    "Action":         ("element", "negated"),
    "CallEvent":      ("api",),
    "CompoundEvent":  ("op", "left", "right"),
    "Guard":          ("op", "left", "right"),
    "BinaryExpr":     ("op", "left", "right"),
    "IncrementExpr":  ("element", "delta"),
    "ReadExpr":       ("element",),
    "LenExpr":        ("element",),
    "StatusExpr":     ("api",),
    "FuncExpr":       ("arg",),
    "LiteralExpr":    ("value",),
    "Range":          (),  # either low+high OR distribution — checked below
}


def _check_required(node: dict) -> dict:
    ntype = node.get("type")
    for field in _REQUIRED.get(ntype, ()):
        if node.get(field) is None and field != "value":
            raise SemanticError(f"{ntype} missing required field '{field}'.")
    # LiteralExpr.value: None is a bug, but "null" / 0 / "" / False are valid
    if ntype == "LiteralExpr" and "value" not in node:
        raise SemanticError("LiteralExpr missing required field 'value'.")
    if ntype == "Range":
        has_bracket = node.get("low") is not None and node.get("high") is not None
        has_dist    = node.get("distribution") is not None
        if not (has_bracket or has_dist):
            raise SemanticError("Range must specify either [low, high] or a distribution.")
    return node


class ASTBuilder(ConstraintVisitor):
    """Build a dict AST from a Constraint parse tree."""

    # ── Top-level ─────────────────────────────────────────────────────────

    def visitConstraint(self, ctx: ConstraintParser.ConstraintContext):
        return self.visit(ctx.prob_constraint())

    def visitProb_constraint(self, ctx: ConstraintParser.Prob_constraintContext):
        logic_exprs = ctx.logic_expr()
        if len(logic_exprs) != 2:
            raise SemanticError("Probabilistic constraint requires an event and a condition.")
        event     = self.visit(logic_exprs[0])
        condition = self.visit(logic_exprs[1])
        prob      = self.visit(ctx.probability_expr())
        return _check_required({
            "type":          "Probabilistic",
            "event":         event,
            "condition":     condition,
            "probability":   prob["probability"],
            "prob_operator": prob["prob_operator"],
        })

    def visitProbability_expr(self, ctx: ConstraintParser.Probability_exprContext):
        op = ctx.getChild(0).getText()
        if op not in ("=", "<", ">", "<=", ">="):
            raise SemanticError(f"Unknown probability operator '{op}'.")
        return {"prob_operator": op, "probability": float(ctx.NUMBER().getText())}

    # ── Boolean logic — fold into CompoundEvent ──────────────────────────

    def visitLogic_expr(self, ctx: ConstraintParser.Logic_exprContext):
        if ctx.getChildCount() == 3 and ctx.OR() is not None:
            return _check_required({
                "type":  "CompoundEvent",
                "op":    "OR",
                "left":  self.visit(ctx.logic_expr()),
                "right": self.visit(ctx.logic_xor()),
            })
        return self.visit(ctx.logic_xor())

    def visitLogic_xor(self, ctx: ConstraintParser.Logic_xorContext):
        if ctx.getChildCount() == 3 and ctx.XOR() is not None:
            return _check_required({
                "type":  "CompoundEvent",
                "op":    "XOR",
                "left":  self.visit(ctx.logic_xor()),
                "right": self.visit(ctx.logic_term()),
            })
        return self.visit(ctx.logic_term())

    def visitLogic_term(self, ctx: ConstraintParser.Logic_termContext):
        if ctx.getChildCount() == 3 and ctx.AND() is not None:
            left  = self.visit(ctx.logic_term())
            right = self.visit(ctx.logic_factor())
            # AND of an Action with a Guard collapses into Action.guard.
            attached = _attach_guard(left, right) or _attach_guard(right, left)
            if attached is not None:
                return attached
            return _check_required({
                "type":  "CompoundEvent",
                "op":    "AND",
                "left":  left,
                "right": right,
            })
        return self.visit(ctx.logic_factor())

    def visitLogic_factor(self, ctx: ConstraintParser.Logic_factorContext):
        if ctx.NOT() is not None:
            inner = self.visit(ctx.logic_factor())
            if inner.get("type") != "Action":
                raise SemanticError("NOT can only be applied to user actions A(...).")
            return _check_required({**inner, "negated": not inner["negated"]})
        if ctx.logic_expr() is not None:
            return self.visit(ctx.logic_expr())
        return self.visit(ctx.atom())

    # ── Atoms ─────────────────────────────────────────────────────────────

    def visitAtom(self, ctx: ConstraintParser.AtomContext):
        for child in (ctx.write_event(), ctx.user_action(), ctx.system_event(),
                      ctx.persist_event(), ctx.guard(), ctx.literal_bool()):
            if child is not None:
                return self.visit(child)
        raise SemanticError("Empty atom — parse tree is malformed.")

    def visitWrite_event(self, ctx: ConstraintParser.Write_eventContext):
        # Three forms:
        #   w(target)                            → value_expr=None, sources=None
        #   w(target, expr)                      → value_expr=<expr>
        #   w(target, sources={r(s1), r(s2)})    → sources=[…]; value_expr=None
        # `sources` is the explicit set-equality form (Row 3 style); the
        # downstream dispatcher uses it for `source_set` instead of
        # walking an arithmetic value_expr.
        value_expr = self.visit(ctx.expr()) if ctx.expr() is not None else None
        sources    = self.visit(ctx.source_set()) if ctx.source_set() is not None else None
        return _check_required({
            "type":       "WriteEvent",
            "element":    self.visit(ctx.ui_element()),
            "value_expr": value_expr,
            "sources":    sources,
        })

    def visitUser_action(self, ctx: ConstraintParser.User_actionContext):
        return _check_required({
            "type":    "Action",
            "element": self.visit(ctx.ui_element()),
            "negated": False,
            "guard":   None,
        })

    def visitSystem_event(self, ctx: ConstraintParser.System_eventContext):
        params = self.visit(ctx.expr()) if ctx.expr() is not None else None
        return _check_required({
            "type":   "CallEvent",
            "api":    self.visit(ctx.api()),
            "params": params,
        })

    def visitPersist_event(self, ctx: ConstraintParser.Persist_eventContext):
        return _check_required({
            "type":    "PersistEvent",
            "element": self.visit(ctx.ui_element()),
        })

    def visitSource_set(self, ctx: ConstraintParser.Source_setContext):
        # source_item alternatives — possibly an empty set.
        return [self.visit(item) for item in (ctx.source_item() or [])]

    def visitSource_item(self, ctx: ConstraintParser.Source_itemContext):
        # Either `r(ui_element)` or `r(api_result)`. ui_element() returns
        # None for the api_result form, which we encode as the sentinel
        # element name "api_result" — matching ReadExpr's existing shape.
        if ctx.ui_element() is not None:
            element = self.visit(ctx.ui_element())
        else:
            element = "api_result"
        return _check_required({
            "type":    "ReadExpr",
            "element": element,
        })

    def visitGuard(self, ctx: ConstraintParser.GuardContext):
        exprs = ctx.expr()
        if ctx.IN() is not None:
            return _check_required({
                "type":  "Guard",
                "op":    "in",
                "left":  self.visit(exprs[0]),
                "right": self.visit(ctx.range_()),
            })
        return _check_required({
            "type":  "Guard",
            "op":    self.visit(ctx.comparator()),
            "left":  self.visit(exprs[0]),
            "right": self.visit(exprs[1]),
        })

    # ── Value expressions ────────────────────────────────────────────────

    def visitExpr(self, ctx: ConstraintParser.ExprContext):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.term())
        op    = ctx.getChild(1).getText()
        left  = self.visit(ctx.expr())
        right = self.visit(ctx.term())
        increment = _to_increment(op, left, right)
        if increment is not None:
            return increment
        return _check_required({"type": "BinaryExpr", "op": op, "left": left, "right": right})

    def visitTerm(self, ctx: ConstraintParser.TermContext):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.factor())
        return _check_required({
            "type":  "BinaryExpr",
            "op":    ctx.getChild(1).getText(),
            "left":  self.visit(ctx.term()),
            "right": self.visit(ctx.factor()),
        })

    def visitFactor(self, ctx: ConstraintParser.FactorContext):
        if ctx.expr() is not None:
            return self.visit(ctx.expr())
        return self.visit(ctx.atom_expr())

    def visitAtom_expr(self, ctx: ConstraintParser.Atom_exprContext):
        head = ctx.getChild(0).getText()
        if head == "r(":
            element = self.visit(ctx.ui_element()) if ctx.ui_element() is not None else "api_result"
            return _check_required({"type": "ReadExpr", "element": element})
        if head == "len(":
            element = self.visit(ctx.ui_element()) if ctx.ui_element() is not None else "api_result"
            return _check_required({"type": "LenExpr", "element": element})
        if head == "status(":
            return _check_required({"type": "StatusExpr", "api": self.visit(ctx.api())})
        if head == "f(":
            return _check_required({"type": "FuncExpr", "arg": self.visit(ctx.expr())})
        return self.visit(ctx.literal())

    # ── Terminals ────────────────────────────────────────────────────────

    def visitUi_element(self, ctx: ConstraintParser.Ui_elementContext):
        ident = ctx.IDENTIFIER()
        if ident is None:
            raise SemanticError("ui_element missing identifier.")
        return ident.getText()

    def visitApi(self, ctx: ConstraintParser.ApiContext):
        ident = ctx.IDENTIFIER()
        if ident is None:
            raise SemanticError("api missing identifier.")
        return ident.getText()

    def visitComparator(self, ctx: ConstraintParser.ComparatorContext):
        return ctx.getText()

    def visitRange(self, ctx: ConstraintParser.RangeContext):
        if ctx.getChild(0).getText() == "D":
            return _check_required({"type": "Range", "distribution": "D"})
        numbers = ctx.NUMBER()
        return _check_required({
            "type": "Range",
            "low":  float(numbers[0].getText()),
            "high": float(numbers[1].getText()),
        })

    def visitLiteral(self, ctx: ConstraintParser.LiteralContext):
        if ctx.NUMBER() is not None:
            raw = ctx.NUMBER().getText()
            value: Any = float(raw) if "." in raw else int(raw)
            return _check_required({"type": "LiteralExpr", "value": value})
        if ctx.STRING() is not None:
            return _check_required({"type": "LiteralExpr", "value": ctx.STRING().getText()[1:-1]})
        # 'null' is the only remaining alternative
        return _check_required({"type": "LiteralExpr", "value": "null"})

    def visitLiteral_bool(self, ctx: ConstraintParser.Literal_boolContext):
        return _check_required({"type": "LiteralExpr", "value": ctx.getText() == "true"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attach_guard(action_side: dict, guard_side: dict) -> dict | None:
    """If one side is a bare Action and the other is a Guard, merge them."""
    if (action_side.get("type") == "Action"
            and action_side.get("guard") is None
            and guard_side.get("type") == "Guard"):
        return {**action_side, "guard": guard_side}
    return None


def _to_increment(op: str, left: dict, right: dict) -> dict | None:
    """Recognise `r(elem) ± NUMBER` as an IncrementExpr."""
    if op not in ("+", "-"):
        return None
    if left.get("type") != "ReadExpr":
        return None
    if right.get("type") != "LiteralExpr" or not isinstance(right.get("value"), (int, float)):
        return None
    delta = right["value"] if op == "+" else -right["value"]
    return _check_required({"type": "IncrementExpr", "element": left["element"], "delta": delta})
