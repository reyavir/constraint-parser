"""Parser/lexer intentionally stubbed until ANTLR is wired into `src.parser`."""

import pytest

from src.parser.lexer import LexerError, tokenize
from src.parser.parser import ParseError, parse


def test_lexer_stub_raises():
    with pytest.raises(LexerError):
        tokenize("P(w(a) | A(b)) = 1")


def test_parser_stub_raises():
    with pytest.raises(ParseError):
        parse("anything")
