from __future__ import annotations

from typing import Any, List

from .ast_nodes import (
    ActionCondition,
    ApiCallEvent,
    ArithExpr,
    CompoundCondition,
    CompoundWriteEvent,
    ElementRef,
    FuncExpr,
    Guard,
    LenExpr,
    NullLiteral,
    NumberLiteral,
    ProbabilisticConstraint,
    RangeExpr,
    ReadExpr,
    StaticConstraint,
    StatusExpr,
    StringLiteral,
    WriteEvent,
)
from .lexer import Token, TokenKind, tokenize


class ParseError(Exception):
    def __init__(self, message: str, token: Token) -> None:
        super().__init__(f"{message} (got {token.kind.name} {token.value!r} at pos {token.pos})")
        self.token = token


_PROB_OPS = {TokenKind.EQUALS, TokenKind.LT, TokenKind.GT, TokenKind.LTE, TokenKind.GTE}
_CMP_OPS = {TokenKind.EQUALS, TokenKind.NEQ, TokenKind.LT, TokenKind.GT, TokenKind.LTE, TokenKind.GTE}


class Parser:
    def __init__(self, tokens: List[Token], source: str = "") -> None:
        self._tokens = tokens
        self._pos = 0
        self._source = source

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.kind != TokenKind.EOF:
            self._pos += 1
        return tok

    def _expect(self, kind: TokenKind) -> Token:
        tok = self._current()
        if tok.kind != kind:
            raise ParseError(f"Expected {kind.name}", tok)
        return self._advance()

    def _match(self, *kinds: TokenKind) -> bool:
        return self._current().kind in kinds

    def parse(self) -> ProbabilisticConstraint | StaticConstraint:
        if self._match(TokenKind.P):
            node = self._parse_probabilistic_constraint()
        else:
            node = self._parse_static_constraint()
        self._expect(TokenKind.EOF)
        return node

    def _parse_probabilistic_constraint(self) -> ProbabilisticConstraint:
        self._expect(TokenKind.P)
        self._expect(TokenKind.LPAREN)
        event = self._parse_event()
        self._expect(TokenKind.PIPE)
        condition = self._parse_condition()
        self._expect(TokenKind.RPAREN)

        op_tok = self._current()
        if op_tok.kind not in _PROB_OPS:
            raise ParseError("Expected probability comparison operator", op_tok)
        self._advance()

        probability = self._parse_probability()
        return ProbabilisticConstraint(
            event=event,
            condition=condition,
            probability_op=op_tok.value,
            probability=probability,
            raw=self._source,
        )

    def _parse_static_constraint(self) -> StaticConstraint:
        tok = self._current()
        if tok.kind == TokenKind.NO_LITERAL:
            self._advance()
            self._expect(TokenKind.LPAREN)
            target = self._parse_element()
            self._expect(TokenKind.RPAREN)
            return StaticConstraint(check_type="no_literal", target=target, raw=self._source)
        if tok.kind == TokenKind.NO_HIDDEN_PARAM:
            self._advance()
            self._expect(TokenKind.LPAREN)
            api_tok = self._expect(TokenKind.API)
            self._expect(TokenKind.RPAREN)
            return StaticConstraint(check_type="no_hidden_param", target=ElementRef(api_tok.value), raw=self._source)
        if tok.kind == TokenKind.HIDDEN_ERRORS:
            self._advance()
            self._expect(TokenKind.LPAREN)
            self._expect(TokenKind.RPAREN)
            return StaticConstraint(check_type="hidden_errors", target=None, raw=self._source)
        raise ParseError("Expected top-level constraint", tok)

    def _parse_event(self) -> Any:
        left = self._parse_event_atom()
        while self._match(TokenKind.AND, TokenKind.XOR):
            op_tok = self._advance()
            right = self._parse_event_atom()
            op = "AND" if op_tok.kind == TokenKind.AND else "XOR"
            left = CompoundWriteEvent(op=op, left=left, right=right)
        return left

    def _parse_event_atom(self) -> Any:
        if self._match(TokenKind.LPAREN):
            self._advance()
            nested = self._parse_event()
            self._expect(TokenKind.RPAREN)
            return nested
        if self._match(TokenKind.W):
            return self._parse_write_event()
        if self._match(TokenKind.CALL):
            return self._parse_call_event()
        return self._parse_guard()

    def _parse_write_event(self) -> WriteEvent:
        self._expect(TokenKind.W)
        self._expect(TokenKind.LPAREN)
        element = self._parse_element()
        value_expr = None
        if self._match(TokenKind.COMMA):
            self._advance()
            value_expr = self._parse_expr()
        self._expect(TokenKind.RPAREN)
        return WriteEvent(element=element, value_expr=value_expr)

    def _parse_call_event(self) -> ApiCallEvent:
        self._expect(TokenKind.CALL)
        self._expect(TokenKind.LPAREN)
        api_tok = self._expect(TokenKind.API)
        self._expect(TokenKind.RPAREN)
        return ApiCallEvent(api_ref=api_tok.value, params=None)

    def _parse_condition(self) -> Any:
        left = self._parse_condition_atom()
        while self._match(TokenKind.AND):
            self._advance()
            right = self._parse_condition_atom()
            left = CompoundCondition(op="AND", left=left, right=right)
        return left

    def _parse_condition_atom(self) -> Any:
        if self._match(TokenKind.NOT, TokenKind.A):
            return self._parse_action_condition()
        if self._match(TokenKind.CALL):
            return self._parse_call_event()
        return self._parse_guard()

    def _parse_action_condition(self) -> ActionCondition:
        negated = False
        if self._match(TokenKind.NOT):
            negated = True
            self._advance()
        self._expect(TokenKind.A)
        self._expect(TokenKind.LPAREN)
        element = self._parse_element()
        self._expect(TokenKind.RPAREN)
        guard = None
        if self._match(TokenKind.COMMA):
            self._advance()
            guard = self._parse_guard()
        return ActionCondition(element=element, negated=negated, guard=guard)

    def _parse_guard(self) -> Guard:
        left = self._parse_expr()
        tok = self._current()
        if tok.kind == TokenKind.IN:
            self._advance()
            return Guard(left=left, op="in", right=self._parse_range())
        if tok.kind in _CMP_OPS:
            self._advance()
            right = self._parse_expr()
            return Guard(left=left, op=tok.value, right=right)
        raise ParseError("Expected comparator or ∈ in guard", tok)

    def _parse_expr(self) -> Any:
        left = self._parse_atom()
        while self._match(TokenKind.PLUS, TokenKind.MINUS):
            op_tok = self._advance()
            right = self._parse_atom()
            left = ArithExpr(left=left, op=op_tok.value, right=right)
        return left

    def _parse_atom(self) -> Any:
        tok = self._current()
        if tok.kind == TokenKind.R:
            return self._parse_read_expr()
        if tok.kind == TokenKind.LEN:
            return self._parse_len_expr()
        if tok.kind == TokenKind.STATUS:
            return self._parse_status_expr()
        if tok.kind == TokenKind.F:
            self._advance()
            self._expect(TokenKind.LPAREN)
            arg = self._parse_expr()
            self._expect(TokenKind.RPAREN)
            return FuncExpr(arg=arg)
        if tok.kind in (TokenKind.NUMBER, TokenKind.STRING, TokenKind.NULL):
            return self._parse_literal()
        raise ParseError("Expected expression atom", tok)

    def _parse_read_expr(self) -> ReadExpr:
        self._expect(TokenKind.R)
        self._expect(TokenKind.LPAREN)
        name = self._parse_identifier_str()
        self._expect(TokenKind.RPAREN)
        last = False
        if self._match(TokenKind.LAST):
            self._advance()
            last = True
        return ReadExpr(source=ElementRef(name), last=last)

    def _parse_len_expr(self) -> LenExpr:
        self._expect(TokenKind.LEN)
        self._expect(TokenKind.LPAREN)
        read_expr = self._parse_read_expr()
        self._expect(TokenKind.RPAREN)
        return LenExpr(arg=read_expr)

    def _parse_status_expr(self) -> StatusExpr:
        self._expect(TokenKind.STATUS)
        self._expect(TokenKind.LPAREN)
        api_tok = self._expect(TokenKind.API)
        self._expect(TokenKind.RPAREN)
        return StatusExpr(api_ref=api_tok.value)

    def _parse_range(self) -> RangeExpr:
        if self._match(TokenKind.D):
            self._advance()
            return RangeExpr(distribution="D")
        self._expect(TokenKind.LBRACKET)
        low_tok = self._expect(TokenKind.NUMBER)
        self._expect(TokenKind.COMMA)
        high_tok = self._expect(TokenKind.NUMBER)
        self._expect(TokenKind.RBRACKET)
        return RangeExpr(low=float(low_tok.value), high=float(high_tok.value))

    def _parse_literal(self) -> NumberLiteral | StringLiteral | NullLiteral:
        tok = self._current()
        if tok.kind == TokenKind.NUMBER:
            self._advance()
            return NumberLiteral(float(tok.value))
        if tok.kind == TokenKind.STRING:
            self._advance()
            return StringLiteral(tok.value)
        if tok.kind == TokenKind.NULL:
            self._advance()
            return NullLiteral()
        raise ParseError("Expected literal", tok)

    def _parse_element(self) -> ElementRef:
        return ElementRef(self._parse_identifier_str())

    def _parse_identifier_str(self) -> str:
        tok = self._current()
        if tok.kind in (TokenKind.IDENTIFIER, TokenKind.API):
            self._advance()
            return tok.value
        raise ParseError("Expected identifier", tok)

    def _parse_probability(self) -> float:
        tok = self._expect(TokenKind.NUMBER)
        value = float(tok.value)
        if not (0.0 <= value <= 1.0):
            raise ParseError(f"Probability must be between 0 and 1, got {value}", tok)
        return value


def parse(source: str) -> ProbabilisticConstraint | StaticConstraint:
    tokens = tokenize(source)
    return Parser(tokens, source=source).parse()
