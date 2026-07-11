# Generated from Constraint.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .ConstraintParser import ConstraintParser
else:
    from ConstraintParser import ConstraintParser

# This class defines a complete listener for a parse tree produced by ConstraintParser.
class ConstraintListener(ParseTreeListener):

    # Enter a parse tree produced by ConstraintParser#constraint.
    def enterConstraint(self, ctx:ConstraintParser.ConstraintContext):
        pass

    # Exit a parse tree produced by ConstraintParser#constraint.
    def exitConstraint(self, ctx:ConstraintParser.ConstraintContext):
        pass


    # Enter a parse tree produced by ConstraintParser#prob_constraint.
    def enterProb_constraint(self, ctx:ConstraintParser.Prob_constraintContext):
        pass

    # Exit a parse tree produced by ConstraintParser#prob_constraint.
    def exitProb_constraint(self, ctx:ConstraintParser.Prob_constraintContext):
        pass


    # Enter a parse tree produced by ConstraintParser#probability_expr.
    def enterProbability_expr(self, ctx:ConstraintParser.Probability_exprContext):
        pass

    # Exit a parse tree produced by ConstraintParser#probability_expr.
    def exitProbability_expr(self, ctx:ConstraintParser.Probability_exprContext):
        pass


    # Enter a parse tree produced by ConstraintParser#logic_expr.
    def enterLogic_expr(self, ctx:ConstraintParser.Logic_exprContext):
        pass

    # Exit a parse tree produced by ConstraintParser#logic_expr.
    def exitLogic_expr(self, ctx:ConstraintParser.Logic_exprContext):
        pass


    # Enter a parse tree produced by ConstraintParser#logic_xor.
    def enterLogic_xor(self, ctx:ConstraintParser.Logic_xorContext):
        pass

    # Exit a parse tree produced by ConstraintParser#logic_xor.
    def exitLogic_xor(self, ctx:ConstraintParser.Logic_xorContext):
        pass


    # Enter a parse tree produced by ConstraintParser#logic_term.
    def enterLogic_term(self, ctx:ConstraintParser.Logic_termContext):
        pass

    # Exit a parse tree produced by ConstraintParser#logic_term.
    def exitLogic_term(self, ctx:ConstraintParser.Logic_termContext):
        pass


    # Enter a parse tree produced by ConstraintParser#logic_factor.
    def enterLogic_factor(self, ctx:ConstraintParser.Logic_factorContext):
        pass

    # Exit a parse tree produced by ConstraintParser#logic_factor.
    def exitLogic_factor(self, ctx:ConstraintParser.Logic_factorContext):
        pass


    # Enter a parse tree produced by ConstraintParser#atom.
    def enterAtom(self, ctx:ConstraintParser.AtomContext):
        pass

    # Exit a parse tree produced by ConstraintParser#atom.
    def exitAtom(self, ctx:ConstraintParser.AtomContext):
        pass


    # Enter a parse tree produced by ConstraintParser#write_event.
    def enterWrite_event(self, ctx:ConstraintParser.Write_eventContext):
        pass

    # Exit a parse tree produced by ConstraintParser#write_event.
    def exitWrite_event(self, ctx:ConstraintParser.Write_eventContext):
        pass


    # Enter a parse tree produced by ConstraintParser#source_set.
    def enterSource_set(self, ctx:ConstraintParser.Source_setContext):
        pass

    # Exit a parse tree produced by ConstraintParser#source_set.
    def exitSource_set(self, ctx:ConstraintParser.Source_setContext):
        pass


    # Enter a parse tree produced by ConstraintParser#source_item.
    def enterSource_item(self, ctx:ConstraintParser.Source_itemContext):
        pass

    # Exit a parse tree produced by ConstraintParser#source_item.
    def exitSource_item(self, ctx:ConstraintParser.Source_itemContext):
        pass


    # Enter a parse tree produced by ConstraintParser#user_action.
    def enterUser_action(self, ctx:ConstraintParser.User_actionContext):
        pass

    # Exit a parse tree produced by ConstraintParser#user_action.
    def exitUser_action(self, ctx:ConstraintParser.User_actionContext):
        pass


    # Enter a parse tree produced by ConstraintParser#system_event.
    def enterSystem_event(self, ctx:ConstraintParser.System_eventContext):
        pass

    # Exit a parse tree produced by ConstraintParser#system_event.
    def exitSystem_event(self, ctx:ConstraintParser.System_eventContext):
        pass


    # Enter a parse tree produced by ConstraintParser#persist_event.
    def enterPersist_event(self, ctx:ConstraintParser.Persist_eventContext):
        pass

    # Exit a parse tree produced by ConstraintParser#persist_event.
    def exitPersist_event(self, ctx:ConstraintParser.Persist_eventContext):
        pass


    # Enter a parse tree produced by ConstraintParser#guard.
    def enterGuard(self, ctx:ConstraintParser.GuardContext):
        pass

    # Exit a parse tree produced by ConstraintParser#guard.
    def exitGuard(self, ctx:ConstraintParser.GuardContext):
        pass


    # Enter a parse tree produced by ConstraintParser#expr.
    def enterExpr(self, ctx:ConstraintParser.ExprContext):
        pass

    # Exit a parse tree produced by ConstraintParser#expr.
    def exitExpr(self, ctx:ConstraintParser.ExprContext):
        pass


    # Enter a parse tree produced by ConstraintParser#term.
    def enterTerm(self, ctx:ConstraintParser.TermContext):
        pass

    # Exit a parse tree produced by ConstraintParser#term.
    def exitTerm(self, ctx:ConstraintParser.TermContext):
        pass


    # Enter a parse tree produced by ConstraintParser#factor.
    def enterFactor(self, ctx:ConstraintParser.FactorContext):
        pass

    # Exit a parse tree produced by ConstraintParser#factor.
    def exitFactor(self, ctx:ConstraintParser.FactorContext):
        pass


    # Enter a parse tree produced by ConstraintParser#atom_expr.
    def enterAtom_expr(self, ctx:ConstraintParser.Atom_exprContext):
        pass

    # Exit a parse tree produced by ConstraintParser#atom_expr.
    def exitAtom_expr(self, ctx:ConstraintParser.Atom_exprContext):
        pass


    # Enter a parse tree produced by ConstraintParser#identifier.
    def enterIdentifier(self, ctx:ConstraintParser.IdentifierContext):
        pass

    # Exit a parse tree produced by ConstraintParser#identifier.
    def exitIdentifier(self, ctx:ConstraintParser.IdentifierContext):
        pass


    # Enter a parse tree produced by ConstraintParser#comparator.
    def enterComparator(self, ctx:ConstraintParser.ComparatorContext):
        pass

    # Exit a parse tree produced by ConstraintParser#comparator.
    def exitComparator(self, ctx:ConstraintParser.ComparatorContext):
        pass


    # Enter a parse tree produced by ConstraintParser#range.
    def enterRange(self, ctx:ConstraintParser.RangeContext):
        pass

    # Exit a parse tree produced by ConstraintParser#range.
    def exitRange(self, ctx:ConstraintParser.RangeContext):
        pass


    # Enter a parse tree produced by ConstraintParser#literal.
    def enterLiteral(self, ctx:ConstraintParser.LiteralContext):
        pass

    # Exit a parse tree produced by ConstraintParser#literal.
    def exitLiteral(self, ctx:ConstraintParser.LiteralContext):
        pass


    # Enter a parse tree produced by ConstraintParser#literal_bool.
    def enterLiteral_bool(self, ctx:ConstraintParser.Literal_boolContext):
        pass

    # Exit a parse tree produced by ConstraintParser#literal_bool.
    def exitLiteral_bool(self, ctx:ConstraintParser.Literal_boolContext):
        pass



del ConstraintParser