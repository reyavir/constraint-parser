"""
Parse a Constraint-language source string into a dict AST.

Pipeline:
    source ──▶ ConstraintLexer ──▶ CommonTokenStream
           ──▶ ConstraintParser.constraint() ──▶ parse tree
           ──▶ ASTBuilder (visitor 1)        ──▶ dict AST

`parse()` is the production entry point and only returns the AST.
`parse_with_steps()` runs the same pipeline but also returns the token stream
and a pretty-printed parse tree so the UI can show each stage for debugging.
"""

from __future__ import annotations

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener
from antlr4.tree.Tree import TerminalNodeImpl

from ConstraintLexer import ConstraintLexer
from ConstraintParser import ConstraintParser

from .ast_visitor import ASTBuilder, SemanticError
from .lexer import Token, _symbol_for


class ParseError(Exception):
    def __init__(self, message: str, line: int = 0, column: int = 0) -> None:
        super().__init__(f"{message} (line {line}, col {column})")
        self.line = line
        self.column = column


class _CollectingErrorListener(ErrorListener):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[tuple[int, int, str]] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append((line, column, msg))


def _build_parser(source: str):
    """Wire a lexer + parser with collecting error listeners."""
    stream = InputStream(source)
    lexer  = ConstraintLexer(stream)
    lex_listener = _CollectingErrorListener()
    lexer.removeErrorListeners()
    lexer.addErrorListener(lex_listener)

    token_stream = CommonTokenStream(lexer)
    parser = ConstraintParser(token_stream)
    parse_listener = _CollectingErrorListener()
    parser.removeErrorListeners()
    parser.addErrorListener(parse_listener)

    return lexer, token_stream, parser, lex_listener, parse_listener


def _raise_if_errors(*listeners: _CollectingErrorListener) -> None:
    for listener in listeners:
        if listener.errors:
            line, col, msg = listener.errors[0]
            raise ParseError(msg, line=line, column=col)


def parse(source: str) -> dict:
    """Return the dict AST for *source*, raising ParseError on syntax errors."""
    if not source.strip():
        raise ParseError("Empty input.")

    _lexer, _tokens, parser, lex_listener, parse_listener = _build_parser(source)
    tree = parser.constraint()
    _raise_if_errors(lex_listener, parse_listener)
    return ASTBuilder().visit(tree)


def parse_with_steps(source: str) -> dict:
    """
    Run the full pipeline and return every stage's output:
        { "tokens": [Token, ...],
          "parse_tree": str,        # indented pretty-print of the parse tree
          "ast": dict }             # Visitor 1 output

    Lex/parse errors are still raised as ParseError; the visitor's own
    SemanticError propagates as-is.
    """
    if not source.strip():
        raise ParseError("Empty input.")

    _lexer, token_stream, parser, lex_listener, parse_listener = _build_parser(source)
    tree = parser.constraint()
    _raise_if_errors(lex_listener, parse_listener)

    tokens: list[Token] = []
    for tok in token_stream.tokens:
        if tok.type == -1:  # EOF
            continue
        tokens.append(Token(kind=_symbol_for(tok.type), value=tok.text, pos=tok.start))

    parse_tree = _format_parse_tree(tree, parser)
    ast = ASTBuilder().visit(tree)

    return {"tokens": tokens, "parse_tree": parse_tree, "ast": ast}


def _format_parse_tree(node, parser: ConstraintParser) -> str:
    """Indented pretty-print of an ANTLR parse tree."""
    lines: list[str] = []

    def walk(n, depth: int) -> None:
        indent = "  " * depth
        if isinstance(n, TerminalNodeImpl):
            text = n.getText()
            if text == "<EOF>":
                return
            lines.append(f"{indent}{text}")
            return
        rule_index = n.getRuleIndex()
        rule_name = parser.ruleNames[rule_index] if 0 <= rule_index < len(parser.ruleNames) else "?"
        lines.append(f"{indent}{rule_name}")
        for i in range(n.getChildCount()):
            walk(n.getChild(i), depth + 1)

    walk(node, 0)
    return "\n".join(lines)


__all__ = ["parse", "parse_with_steps", "ParseError", "SemanticError"]
