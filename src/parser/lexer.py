"""
Tokenise Constraint language input using the ANTLR-generated ConstraintLexer.

Exposes a small `Token` record (kind/value/pos) so the serializer + UI panel
can categorise tokens without depending on ANTLR internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from ConstraintLexer import ConstraintLexer
from ConstraintParser import ConstraintParser  # name tables indexed by token type


@dataclass(frozen=True)
class Token:
    kind: str        # symbolic name from ANTLR (e.g. IDENTIFIER, NUMBER, AND) or literal text
    value: str       # raw source text
    pos: int         # absolute character offset


class LexerError(Exception):
    def __init__(self, message: str, pos: int) -> None:
        super().__init__(f"{message} (position {pos})")
        self.pos = pos


class _CollectingErrorListener(ErrorListener):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[tuple[int, int, str]] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append((line, column, msg))


def _symbol_for(token_type: int) -> str:
    """
    Best-effort name for a token type. We read from the parser's name tables,
    which are indexed by token type (the lexer's lists are declaration-ordered
    and not safe to index that way).
    """
    names = ConstraintParser.symbolicNames
    if 0 <= token_type < len(names) and names[token_type] not in (None, "<INVALID>"):
        return names[token_type]
    lits = ConstraintParser.literalNames
    if 0 <= token_type < len(lits) and lits[token_type] not in (None, "<INVALID>"):
        return lits[token_type].strip("'")
    return "TOKEN"


def tokenize(source: str) -> List[Token]:
    if not source.strip():
        raise LexerError("Empty input.", 0)

    stream  = InputStream(source)
    lexer   = ConstraintLexer(stream)
    listener = _CollectingErrorListener()
    lexer.removeErrorListeners()
    lexer.addErrorListener(listener)

    token_stream = CommonTokenStream(lexer)
    token_stream.fill()

    if listener.errors:
        _line, col, msg = listener.errors[0]
        raise LexerError(msg, col)

    out: List[Token] = []
    for tok in token_stream.tokens:
        if tok.type == -1:    # EOF
            continue
        out.append(Token(
            kind  = _symbol_for(tok.type),
            value = tok.text,
            pos   = tok.start,
        ))
    return out
