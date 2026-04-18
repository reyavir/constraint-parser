"""
Lexer for the constraint language.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class TokenKind(Enum):
    P = "P"
    A = "A"
    W = "w"
    R = "r"
    F = "f"
    CALL = "call"
    LEN = "len"
    STATUS = "status"
    NO_LITERAL = "no_literal"
    NO_HIDDEN_PARAM = "no_hidden_param"
    HIDDEN_ERRORS = "hidden_errors"
    XOR = "XOR"
    NULL = "null"
    D = "D"
    API = "api"

    NUMBER = "NUMBER"
    STRING = "STRING"
    IDENTIFIER = "IDENTIFIER"

    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    PIPE = "|"
    COMMA = ","
    EQUALS = "="

    NOT = "NOT"
    AND = "AND"
    IN = "IN"

    PLUS = "+"
    MINUS = "-"

    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="
    NEQ = "!="

    LAST = "_last"
    EOF = "EOF"


_KEYWORDS: dict[str, TokenKind] = {
    "P": TokenKind.P,
    "A": TokenKind.A,
    "w": TokenKind.W,
    "r": TokenKind.R,
    "f": TokenKind.F,
    "call": TokenKind.CALL,
    "len": TokenKind.LEN,
    "status": TokenKind.STATUS,
    "no_literal": TokenKind.NO_LITERAL,
    "no_hidden_param": TokenKind.NO_HIDDEN_PARAM,
    "hidden_errors": TokenKind.HIDDEN_ERRORS,
    "XOR": TokenKind.XOR,
    "null": TokenKind.NULL,
    "_last": TokenKind.LAST,
    "D": TokenKind.D,
    "api": TokenKind.API,
}


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    pos: int


class LexerError(Exception):
    def __init__(self, message: str, pos: int) -> None:
        super().__init__(f"{message} (position {pos})")
        self.pos = pos


class Lexer:
    def __init__(self, source: str) -> None:
        self._src = source
        self._pos = 0
        self._tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        while self._pos < len(self._src):
            self._skip_whitespace()
            if self._pos >= len(self._src):
                break
            self._scan_one()
        self._tokens.append(Token(TokenKind.EOF, "", self._pos))
        return self._tokens

    def _ch(self) -> str:
        return self._src[self._pos]

    def _peek(self, offset: int = 1) -> str:
        idx = self._pos + offset
        return self._src[idx] if idx < len(self._src) else ""

    def _emit(self, kind: TokenKind, value: str, start: int) -> None:
        self._tokens.append(Token(kind, value, start))

    def _skip_whitespace(self) -> None:
        while self._pos < len(self._src) and self._src[self._pos] in " \t\n\r":
            self._pos += 1

    def _scan_one(self) -> None:
        start = self._pos
        ch = self._ch()
        two = self._src[self._pos : self._pos + 2]

        if ch == "¬":
            self._emit(TokenKind.NOT, ch, start)
            self._pos += 1
            return
        if ch == "∧":
            self._emit(TokenKind.AND, ch, start)
            self._pos += 1
            return
        if ch == "∈":
            self._emit(TokenKind.IN, ch, start)
            self._pos += 1
            return

        if two == "<=":
            self._emit(TokenKind.LTE, two, start)
            self._pos += 2
            return
        if two == ">=":
            self._emit(TokenKind.GTE, two, start)
            self._pos += 2
            return
        if two == "!=":
            self._emit(TokenKind.NEQ, two, start)
            self._pos += 2
            return
        if two == "&&":
            self._emit(TokenKind.AND, two, start)
            self._pos += 2
            return

        single = {
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            "[": TokenKind.LBRACKET,
            "]": TokenKind.RBRACKET,
            "|": TokenKind.PIPE,
            ",": TokenKind.COMMA,
            "=": TokenKind.EQUALS,
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "<": TokenKind.LT,
            ">": TokenKind.GT,
            "!": TokenKind.NOT,
        }
        if ch in single:
            self._emit(single[ch], ch, start)
            self._pos += 1
            return

        if ch.isdigit() or (ch == "." and self._peek().isdigit()):
            self._scan_number(start)
            return

        if ch == '"':
            self._scan_string(start)
            return

        if ch.isalpha() or ch == "_":
            self._scan_word(start)
            return

        raise LexerError(f"Unexpected character {ch!r}", start)

    def _scan_number(self, start: int) -> None:
        has_dot = False
        while self._pos < len(self._src):
            c = self._src[self._pos]
            if c.isdigit():
                self._pos += 1
            elif c == "." and not has_dot and self._peek().isdigit():
                has_dot = True
                self._pos += 1
            else:
                break
        self._emit(TokenKind.NUMBER, self._src[start : self._pos], start)

    def _scan_string(self, start: int) -> None:
        self._pos += 1
        while self._pos < len(self._src) and self._src[self._pos] != '"':
            self._pos += 1
        if self._pos >= len(self._src):
            raise LexerError("Unterminated string literal", start)
        self._pos += 1
        self._emit(TokenKind.STRING, self._src[start + 1 : self._pos - 1], start)

    def _scan_word(self, start: int) -> None:
        while self._pos < len(self._src) and (
            self._src[self._pos].isalnum() or self._src[self._pos] == "_"
        ):
            self._pos += 1
        word = self._src[start : self._pos]
        kind = _KEYWORDS.get(word, TokenKind.IDENTIFIER)
        self._emit(kind, word, start)


def tokenize(source: str) -> List[Token]:
    return Lexer(source).tokenize()
