"""
Lexer for the constraint language.

Converts a raw constraint string into a flat list of tokens.
All reserved words are case-sensitive.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenKind(Enum):
    # ── Reserved words ──────────────────────────────────────────────────────
    P        = "P"
    A        = "A"
    W        = "w"
    R        = "r"
    F        = "f"
    CALL     = "call"
    SEQ      = "seq"
    LEN      = "len"
    ERROR    = "error"
    STATUS   = "status"
    STATIC   = "static"
    XOR      = "XOR"
    IN       = "in"
    NULL     = "null"
    # ── Literals ─────────────────────────────────────────────────────────────
    NUMBER   = "NUMBER"
    STRING   = "STRING"
    IDENTIFIER = "IDENTIFIER"
    # ── Punctuation ──────────────────────────────────────────────────────────
    LPAREN   = "("
    RPAREN   = ")"
    PIPE     = "|"
    COMMA    = ","
    EQUALS   = "="
    COLON    = ":"
    # ── Logical / negation ───────────────────────────────────────────────────
    NOT      = "NOT"    # ¬ or !  (prefix negation only)
    AND      = "AND"    # ∧ or &&
    # ── Arithmetic ───────────────────────────────────────────────────────────
    PLUS     = "+"
    MINUS    = "-"
    TIMES    = "*"
    DIVIDE   = "/"
    # ── Comparison ───────────────────────────────────────────────────────────
    LT       = "<"
    GT       = ">"
    LTE      = "<="
    GTE      = ">="
    EQ       = "=="
    NEQ      = "!="
    # ── Special ──────────────────────────────────────────────────────────────
    LAST     = "_last"  # value_expr modifier
    EOF      = "EOF"


# Words that map to a specific TokenKind instead of IDENTIFIER.
_KEYWORDS: dict[str, TokenKind] = {
    "P":      TokenKind.P,
    "A":      TokenKind.A,
    "w":      TokenKind.W,
    "r":      TokenKind.R,
    "f":      TokenKind.F,
    "call":   TokenKind.CALL,
    "seq":    TokenKind.SEQ,
    "len":    TokenKind.LEN,
    "error":  TokenKind.ERROR,
    "status": TokenKind.STATUS,
    "static": TokenKind.STATIC,
    "XOR":    TokenKind.XOR,
    "in":     TokenKind.IN,
    "null":   TokenKind.NULL,
    "_last":  TokenKind.LAST,
}


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    pos: int   # byte offset in the source string (for error messages)

    def __repr__(self) -> str:
        return f"Token({self.kind.name}, {self.value!r}, pos={self.pos})"


class LexerError(Exception):
    def __init__(self, message: str, pos: int) -> None:
        super().__init__(f"{message} (position {pos})")
        self.pos = pos


class Lexer:
    """Tokenises a single constraint string."""

    def __init__(self, source: str) -> None:
        self._src = source
        self._pos = 0
        self._tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        """Return the full token list, including a trailing EOF token."""
        while self._pos < len(self._src):
            self._skip_whitespace()
            if self._pos >= len(self._src):
                break
            self._scan_one()

        self._tokens.append(Token(TokenKind.EOF, "", self._pos))
        return self._tokens

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

        # ── Unicode negation ────────────────────────────────────────────────
        if ch == "¬":
            self._emit(TokenKind.NOT, "¬", start)
            self._pos += 1
            return

        # ── Unicode AND ────────────────────────────────────────────────────
        if ch == "∧":
            self._emit(TokenKind.AND, "∧", start)
            self._pos += 1
            return

        # ── Two-character tokens ────────────────────────────────────────────
        two = self._src[self._pos : self._pos + 2]
        if two == "&&":
            self._emit(TokenKind.AND, "&&", start)
            self._pos += 2
            return
        if two == "<=":
            self._emit(TokenKind.LTE, "<=", start)
            self._pos += 2
            return
        if two == ">=":
            self._emit(TokenKind.GTE, ">=", start)
            self._pos += 2
            return
        if two == "==":
            self._emit(TokenKind.EQ, "==", start)
            self._pos += 2
            return
        if two == "!=":
            self._emit(TokenKind.NEQ, "!=", start)
            self._pos += 2
            return

        # ── Single-character tokens ─────────────────────────────────────────
        _single: dict[str, TokenKind] = {
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            "|": TokenKind.PIPE,
            ",": TokenKind.COMMA,
            "=": TokenKind.EQUALS,
            ":": TokenKind.COLON,
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "*": TokenKind.TIMES,
            "/": TokenKind.DIVIDE,
            "<": TokenKind.LT,
            ">": TokenKind.GT,
            "!": TokenKind.NOT,   # bare ! (not followed by =, handled above)
        }
        if ch in _single:
            self._emit(_single[ch], ch, start)
            self._pos += 1
            return

        # ── Numeric literal ─────────────────────────────────────────────────
        if ch.isdigit() or (ch == "." and self._peek().isdigit()):
            self._scan_number(start)
            return

        # ── String literal ──────────────────────────────────────────────────
        if ch == '"':
            self._scan_string(start)
            return

        # ── Identifier or keyword (includes _last) ──────────────────────────
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
        self._pos += 1  # consume opening "
        while self._pos < len(self._src) and self._src[self._pos] != '"':
            self._pos += 1
        if self._pos >= len(self._src):
            raise LexerError("Unterminated string literal", start)
        self._pos += 1  # consume closing "
        # value excludes the quotes
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
    """Convenience function — tokenise *source* and return the token list."""
    return Lexer(source).tokenize()
