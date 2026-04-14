"""
Recursive-descent parser for the constraint language.

Entry point
-----------
    from src.parser import parse

    ast = parse("P(w(cartDisplay) | A(addBtn)) = 1")

The parser raises ParseError on any syntax violation, with a message that
includes the position and the unexpected token.
"""

from __future__ import annotations
from typing import List, Optional, Any

from .lexer import Token, TokenKind, tokenize
from .ast_nodes import (
    ElementRef,
    NumberLiteral,
    StringLiteral,
    NullLiteral,
    ReadExpr,
    FuncExpr,
    ArithExpr,
    WriteEvent,
    CompoundWriteEvent,
    SeqOrderEvent,
    LenMatchEvent,
    ApiCallEvent,
    Guard,
    ActionCondition,
    ApiErrorCondition,
    ApiStatusCondition,
    ProbabilisticConstraint,
    StaticConstraint,
)


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class ParseError(Exception):
    def __init__(self, message: str, token: Token) -> None:
        super().__init__(f"{message} (got {token.kind.name} {token.value!r} at pos {token.pos})")
        self.token = token


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_ARITH_OPS = {TokenKind.PLUS, TokenKind.MINUS, TokenKind.TIMES, TokenKind.DIVIDE}
_COMPARE_OPS = {TokenKind.LT, TokenKind.GT, TokenKind.LTE, TokenKind.GTE, TokenKind.EQ, TokenKind.NEQ}


class Parser:
    """
    Recursive-descent parser.  Each parse_* method consumes tokens from
    self._tokens[self._pos:] and returns an AST node (or raises ParseError).
    """

    def __init__(self, tokens: List[Token], source: str = "") -> None:
        self._tokens = tokens
        self._pos = 0
        self._source = source

    # ------------------------------------------------------------------
    # Token primitives
    # ------------------------------------------------------------------

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]  # EOF

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

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def parse(self) -> ProbabilisticConstraint | StaticConstraint:
        if self._match(TokenKind.STATIC):
            node = self._parse_static_constraint()
        else:
            node = self._parse_probabilistic_constraint()
        self._expect(TokenKind.EOF)
        return node

    # ------------------------------------------------------------------
    # Static constraint:  static:check_type(target)
    # ------------------------------------------------------------------

    def _parse_static_constraint(self) -> StaticConstraint:
        start_tok = self._expect(TokenKind.STATIC)
        self._expect(TokenKind.COLON)
        check_type_tok = self._current()
        if check_type_tok.kind not in (TokenKind.IDENTIFIER, TokenKind.NULL):
            raise ParseError("Expected static check type identifier", check_type_tok)
        self._advance()
        self._expect(TokenKind.LPAREN)
        target = self._parse_element()
        self._expect(TokenKind.RPAREN)
        return StaticConstraint(
            check_type=check_type_tok.value,
            target=target,
            raw=self._source,
        )

    # ------------------------------------------------------------------
    # Probabilistic constraint:  P(event | condition) = probability
    # ------------------------------------------------------------------

    def _parse_probabilistic_constraint(self) -> ProbabilisticConstraint:
        self._expect(TokenKind.P)
        self._expect(TokenKind.LPAREN)
        event = self._parse_event()
        self._expect(TokenKind.PIPE)
        condition = self._parse_condition()
        self._expect(TokenKind.RPAREN)
        self._expect(TokenKind.EQUALS)
        probability = self._parse_probability()
        return ProbabilisticConstraint(
            event=event,
            condition=condition,
            probability=probability,
            raw=self._source,
        )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _parse_event(self) -> Any:
        """
        event ::= compound_event
        compound_event dispatches on the leading keyword.
        """
        if self._match(TokenKind.SEQ):
            return self._parse_seq_event()
        if self._match(TokenKind.LEN):
            return self._parse_len_event()
        if self._match(TokenKind.CALL):
            return self._parse_api_call_event()

        # Write event — may be followed by ∧ or XOR
        write = self._parse_write_event()

        if self._match(TokenKind.AND):
            self._advance()
            right = self._parse_write_event()
            return CompoundWriteEvent(op="AND", left=write, right=right)

        if self._match(TokenKind.XOR):
            self._advance()
            right = self._parse_write_event()
            return CompoundWriteEvent(op="XOR", left=write, right=right)

        return write

    def _parse_write_event(self) -> WriteEvent:
        """write_event ::= "w" "(" element ("," value_expr)? ")" """
        self._expect(TokenKind.W)
        self._expect(TokenKind.LPAREN)
        element = self._parse_element()
        value_expr = None
        if self._match(TokenKind.COMMA):
            self._advance()
            value_expr = self._parse_value_expr()
        self._expect(TokenKind.RPAREN)
        return WriteEvent(element=element, value_expr=value_expr)

    def _parse_seq_event(self) -> SeqOrderEvent:
        """seq_event ::= "seq" "(" write_event ")" "<" "seq" "(" write_event ")" """
        self._expect(TokenKind.SEQ)
        self._expect(TokenKind.LPAREN)
        first = self._parse_write_event()
        self._expect(TokenKind.RPAREN)
        self._expect(TokenKind.LT)
        self._expect(TokenKind.SEQ)
        self._expect(TokenKind.LPAREN)
        second = self._parse_write_event()
        self._expect(TokenKind.RPAREN)
        return SeqOrderEvent(first=first, second=second)

    def _parse_len_event(self) -> LenMatchEvent:
        """len_event ::= "len" "(" read_expr ")" "=" "len" "(" read_expr ")" """
        self._expect(TokenKind.LEN)
        self._expect(TokenKind.LPAREN)
        left = self._parse_read_expr()
        self._expect(TokenKind.RPAREN)
        self._expect(TokenKind.EQUALS)
        self._expect(TokenKind.LEN)
        self._expect(TokenKind.LPAREN)
        right = self._parse_read_expr()
        self._expect(TokenKind.RPAREN)
        return LenMatchEvent(left=left, right=right)

    def _parse_api_call_event(self) -> ApiCallEvent:
        """call_event ::= "call" "(" api_ref ("," value_expr)? ")" """
        self._expect(TokenKind.CALL)
        self._expect(TokenKind.LPAREN)
        api_ref = self._parse_identifier_str()
        params = None
        if self._match(TokenKind.COMMA):
            self._advance()
            params = self._parse_value_expr()
        self._expect(TokenKind.RPAREN)
        return ApiCallEvent(api_ref=api_ref, params=params)

    # ------------------------------------------------------------------
    # Conditions
    # ------------------------------------------------------------------

    def _parse_condition(self) -> Any:
        """
        condition ::= NOT? "A" "(" element ")" ("," guard)?
                    | "error" "(" api_ref ")"
                    | "status" "(" api_ref ")" COMPARE_OP NUMBER
        """
        if self._match(TokenKind.ERROR):
            return self._parse_api_error_condition()

        if self._match(TokenKind.STATUS):
            return self._parse_api_status_condition()

        return self._parse_action_condition()

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

    def _parse_api_error_condition(self) -> ApiErrorCondition:
        self._expect(TokenKind.ERROR)
        self._expect(TokenKind.LPAREN)
        api_ref = self._parse_identifier_str()
        self._expect(TokenKind.RPAREN)
        return ApiErrorCondition(api_ref=api_ref)

    def _parse_api_status_condition(self) -> ApiStatusCondition:
        self._expect(TokenKind.STATUS)
        self._expect(TokenKind.LPAREN)
        api_ref = self._parse_identifier_str()
        self._expect(TokenKind.RPAREN)
        op_tok = self._current()
        if op_tok.kind not in _COMPARE_OPS:
            raise ParseError("Expected comparison operator after status(...)", op_tok)
        self._advance()
        num_tok = self._expect(TokenKind.NUMBER)
        return ApiStatusCondition(
            api_ref=api_ref,
            op=op_tok.value,
            status_code=float(num_tok.value),
        )

    def _parse_guard(self) -> Guard:
        """guard ::= "r" "(" element ")" ("=" | "!=" | "in") literal_or_set"""
        self._expect(TokenKind.R)
        self._expect(TokenKind.LPAREN)
        element = self._parse_element()
        self._expect(TokenKind.RPAREN)

        op_tok = self._current()
        if op_tok.kind == TokenKind.EQUALS:
            op = "="
            self._advance()
        elif op_tok.kind == TokenKind.NEQ:
            op = "!="
            self._advance()
        elif op_tok.kind == TokenKind.IN:
            op = "in"
            self._advance()
        else:
            raise ParseError("Expected '=', '!=', or 'in' in guard", op_tok)

        if op == "in":
            # value is a set/range name (an identifier)
            set_name = self._parse_identifier_str()
            return Guard(element=element, op=op, value=set_name)

        value = self._parse_literal()
        return Guard(element=element, op=op, value=value)

    # ------------------------------------------------------------------
    # Value expressions
    # ------------------------------------------------------------------

    def _parse_value_expr(self) -> Any:
        """value_expr ::= arith_expr  (left-associative, same precedence)"""
        return self._parse_arith_expr()

    def _parse_arith_expr(self) -> Any:
        """arith_expr ::= primary (ARITH_OP primary)*"""
        left = self._parse_primary()
        while self._match(*_ARITH_OPS):
            op_tok = self._advance()
            right = self._parse_primary()
            left = ArithExpr(left=left, op=op_tok.value, right=right)
        return left

    def _parse_primary(self) -> Any:
        """
        primary ::= read_expr "_last"?
                  | "f" "(" value_expr ")"
                  | "(" value_expr ")"
                  | literal
        """
        tok = self._current()

        if tok.kind == TokenKind.R:
            node = self._parse_read_expr()
            # Optional _last modifier
            if self._match(TokenKind.LAST):
                self._advance()
                # ReadExpr is frozen; rebuild with last=True
                node = ReadExpr(source=node.source, last=True)
            return node

        if tok.kind == TokenKind.F:
            self._advance()
            self._expect(TokenKind.LPAREN)
            arg = self._parse_value_expr()
            self._expect(TokenKind.RPAREN)
            return FuncExpr(arg=arg)

        if tok.kind == TokenKind.LPAREN:
            self._advance()
            inner = self._parse_value_expr()
            self._expect(TokenKind.RPAREN)
            return inner

        return self._parse_literal()

    def _parse_read_expr(self) -> ReadExpr:
        """read_expr ::= "r" "(" (element | "api_result") ")" """
        self._expect(TokenKind.R)
        self._expect(TokenKind.LPAREN)
        # "api_result" is an identifier token with value "api_result"
        name = self._parse_identifier_str()
        self._expect(TokenKind.RPAREN)
        return ReadExpr(source=ElementRef(name))

    # ------------------------------------------------------------------
    # Literals and identifiers
    # ------------------------------------------------------------------

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
        raise ParseError("Expected a literal (number, string, or null)", tok)

    def _parse_element(self) -> ElementRef:
        return ElementRef(self._parse_identifier_str())

    def _parse_identifier_str(self) -> str:
        """Consume an identifier-like token and return its string value."""
        tok = self._current()
        # Allow any keyword to be used as an element/api name in argument
        # position (e.g. an element literally named "status" or "error").
        if tok.kind in (TokenKind.IDENTIFIER, *_KEYWORD_TOKENS):
            self._advance()
            return tok.value
        raise ParseError("Expected identifier", tok)

    def _parse_probability(self) -> float:
        tok = self._expect(TokenKind.NUMBER)
        value = float(tok.value)
        if not (0.0 <= value <= 1.0):
            raise ParseError(
                f"Probability must be between 0 and 1, got {value}", tok
            )
        return value


# All TokenKinds that correspond to reserved words (so they can appear as
# element/api names in argument position without being rejected).
_KEYWORD_TOKENS = {
    TokenKind.P, TokenKind.A, TokenKind.W, TokenKind.R, TokenKind.F,
    TokenKind.CALL, TokenKind.SEQ, TokenKind.LEN, TokenKind.ERROR,
    TokenKind.STATUS, TokenKind.STATIC, TokenKind.XOR, TokenKind.IN,
    TokenKind.NULL,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(source: str) -> ProbabilisticConstraint | StaticConstraint:
    """
    Parse a constraint string and return its AST node.

    Raises
    ------
    LexerError
        If the input contains characters that cannot be tokenised.
    ParseError
        If the token stream does not match the grammar.
    """
    tokens = tokenize(source)
    return Parser(tokens, source=source).parse()
