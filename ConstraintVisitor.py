# Generated from Constraint.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .ConstraintParser import ConstraintParser
else:
    from ConstraintParser import ConstraintParser

# This class defines a complete generic visitor for a parse tree produced by ConstraintParser.

class ConstraintVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by ConstraintParser#constraint.
    def visitConstraint(self, ctx:ConstraintParser.ConstraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#prob_constraint.
    def visitProb_constraint(self, ctx:ConstraintParser.Prob_constraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#probability_expr.
    def visitProbability_expr(self, ctx:ConstraintParser.Probability_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#logic_expr.
    def visitLogic_expr(self, ctx:ConstraintParser.Logic_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#logic_xor.
    def visitLogic_xor(self, ctx:ConstraintParser.Logic_xorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#logic_term.
    def visitLogic_term(self, ctx:ConstraintParser.Logic_termContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#logic_factor.
    def visitLogic_factor(self, ctx:ConstraintParser.Logic_factorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#atom.
    def visitAtom(self, ctx:ConstraintParser.AtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#write_event.
    def visitWrite_event(self, ctx:ConstraintParser.Write_eventContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#source_set.
    def visitSource_set(self, ctx:ConstraintParser.Source_setContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#source_item.
    def visitSource_item(self, ctx:ConstraintParser.Source_itemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#user_action.
    def visitUser_action(self, ctx:ConstraintParser.User_actionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#system_event.
    def visitSystem_event(self, ctx:ConstraintParser.System_eventContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#persist_event.
    def visitPersist_event(self, ctx:ConstraintParser.Persist_eventContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#guard.
    def visitGuard(self, ctx:ConstraintParser.GuardContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#expr.
    def visitExpr(self, ctx:ConstraintParser.ExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#term.
    def visitTerm(self, ctx:ConstraintParser.TermContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#factor.
    def visitFactor(self, ctx:ConstraintParser.FactorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#atom_expr.
    def visitAtom_expr(self, ctx:ConstraintParser.Atom_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#ui_element.
    def visitUi_element(self, ctx:ConstraintParser.Ui_elementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#api.
    def visitApi(self, ctx:ConstraintParser.ApiContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#comparator.
    def visitComparator(self, ctx:ConstraintParser.ComparatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#range.
    def visitRange(self, ctx:ConstraintParser.RangeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#literal.
    def visitLiteral(self, ctx:ConstraintParser.LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by ConstraintParser#literal_bool.
    def visitLiteral_bool(self, ctx:ConstraintParser.Literal_boolContext):
        return self.visitChildren(ctx)



del ConstraintParser