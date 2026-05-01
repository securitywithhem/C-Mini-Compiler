import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Iterator, List, Optional, Tuple


class TokenType(Enum):
    KEYWORD = auto()
    IDENTIFIER = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    CHAR = auto()
    OPERATOR = auto()
    SEPARATOR = auto()
    COMMENT = auto()
    PREPROCESSOR = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    column: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.column})"


@dataclass
class SymbolEntry:
    name: str
    occurrences: list[tuple[int, int]] = field(default_factory=list)  # (line, col)

    def add_occurrence(self, line: int, col: int):
        self.occurrences.append((line, col))


C_KEYWORDS = frozenset({
    "auto", "break", "case", "char", "const", "continue", "default",
    "do", "double", "else", "enum", "extern", "float", "for", "goto",
    "if", "inline", "int", "long", "register", "restrict", "return",
    "short", "signed", "sizeof", "static", "struct", "switch", "typedef",
    "union", "unsigned", "void", "volatile", "while",
    "_Bool", "_Complex", "_Imaginary",
})

# Each entry: (name, pattern_without_outer_group, TokenType or None)
# All inner groups must be non-capturing (?:...) so one match group == one pattern.
_TOKEN_SPECS: List[Tuple[str, str, Optional[TokenType]]] = [
    ("LINE_COMMENT",  r"//[^\n]*",                                        TokenType.COMMENT),
    ("BLOCK_COMMENT", r"/\*.*?\*/",                                       TokenType.COMMENT),
    ("PREPROC",       r"#[^\n]*",                                         TokenType.PREPROCESSOR),
    ("STRING",        r'"(?:[^"\\]|\\.)*"',                               TokenType.STRING),
    ("CHAR",          r"'(?:[^'\\]|\\.)'",                                TokenType.CHAR),
    ("FLOAT1",        r"\b\d+\.\d*(?:[eE][+-]?\d+)?[fFlL]?\b",           TokenType.FLOAT),
    ("FLOAT2",        r"\b\.\d+(?:[eE][+-]?\d+)?[fFlL]?\b",              TokenType.FLOAT),
    ("FLOAT3",        r"\b\d+(?:[eE][+-]?\d+)[fFlL]?\b",                 TokenType.FLOAT),
    ("HEX",           r"\b0[xX][0-9a-fA-F]+[uUlL]*\b",                  TokenType.INTEGER),
    ("OCT",           r"\b0[0-7]+[uUlL]*\b",                             TokenType.INTEGER),
    ("INT",           r"\b\d+[uUlL]*\b",                                  TokenType.INTEGER),
    ("IDENT",         r"[a-zA-Z_]\w*",                                    TokenType.IDENTIFIER),
    ("OP3",           r"<<=|>>=|\.\.\.",                                  TokenType.OPERATOR),
    ("OP2",           r"<<|>>|\+\+|--|&&|\|\||[=!<>]=|->|\+=|-=|\*=|/=|%=|&=|\|=|\^=", TokenType.OPERATOR),
    ("OP1",           r"[+\-*/%&|^~!<>=?:]",                             TokenType.OPERATOR),
    ("SEP",           r"[(){}\[\];,.]",                                   TokenType.SEPARATOR),
    ("SPACE",         r"\s+",                                             None),
]

_MASTER_RE = re.compile(
    "|".join(f"(?P<{name}>{pat})" for name, pat, _ in _TOKEN_SPECS),
    re.DOTALL,
)
_TYPE_BY_NAME: Dict[str, Optional[TokenType]] = {name: tt for name, _, tt in _TOKEN_SPECS}


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"{message} at line {line}, col {col}")
        self.line = line
        self.col = col


def _advance_lines(value: str, line: int, line_start: int, end: int) -> tuple[int, int]:
    """Return updated (line, line_start) after consuming `value` ending at `end`."""
    nl = value.count("\n")
    if nl:
        line += nl
        line_start = end - (len(value) - value.rfind("\n") - 1)
    return line, line_start


def _iter_tokens(source: str) -> Iterator[Token]:
    line = 1
    line_start = 0

    for match in _MASTER_RE.finditer(source):
        start = match.start()
        group_name = match.lastgroup
        token_type = _TYPE_BY_NAME[group_name]
        value = match.group()

        # Catch up line/col tracking for any newlines between last match and here
        skipped = source[line_start:start]
        nl = skipped.count("\n")
        if nl:
            line += nl
            line_start = start - (len(skipped) - skipped.rfind("\n") - 1)

        col = start - line_start + 1

        if token_type is None or token_type is TokenType.COMMENT or token_type is TokenType.PREPROCESSOR:
            line, line_start = _advance_lines(value, line, line_start, match.end())
            if token_type is TokenType.PREPROCESSOR:
                yield Token(type=token_type, value=value, line=line, column=col)
            continue

        if token_type is TokenType.IDENTIFIER and value in C_KEYWORDS:
            token_type = TokenType.KEYWORD

        yield Token(type=token_type, value=value, line=line, column=col)
        line, line_start = _advance_lines(value, line, line_start, match.end())



class Lexer:
    def __init__(self):
        self._tokens: list[Token] = []
        self._symbol_table: dict[str, SymbolEntry] = {}

    def tokenize(self, source: str) -> list[Token]:
        self._tokens = []
        self._symbol_table = {}

        for tok in _iter_tokens(source):
            self._tokens.append(tok)
            if tok.type is TokenType.IDENTIFIER:
                entry = self._symbol_table.setdefault(tok.value, SymbolEntry(name=tok.value))
                entry.add_occurrence(tok.line, tok.column)

        return self._tokens

    def get_symbol_table(self) -> dict[str, SymbolEntry]:
        return dict(self._symbol_table)

    def tokens_by_type(self, token_type: TokenType) -> list[Token]:
        return [t for t in self._tokens if t.type is token_type]

    def print_tokens(self):
        header = f"{'TYPE':<15} {'VALUE':<30} {'LINE':>6} {'COL':>6}"
        print(header)
        print("-" * len(header))
        for tok in self._tokens:
            print(f"{tok.type.name:<15} {tok.value!r:<30} {tok.line:>6} {tok.column:>6}")

    def print_symbol_table(self):
        print(f"\n{'IDENTIFIER':<30} {'OCCURRENCES'}")
        print("-" * 60)
        for name, entry in sorted(self._symbol_table.items()):
            locs = ", ".join(f"({l},{c})" for l, c in entry.occurrences)
            print(f"{name:<30} {locs}")


_default_lexer = Lexer()


def tokenize_file(filename: str) -> list[Token]:
    """Read a C source file and return a list of Token objects."""
    with open(filename, encoding="utf-8", errors="replace") as fh:
        source = fh.read()
    return _default_lexer.tokenize(source)


def tokenize_string(source: str) -> list[Token]:
    """Tokenize a C source string directly."""
    return _default_lexer.tokenize(source)


def get_symbol_table() -> dict[str, SymbolEntry]:
    """Return the symbol table built from the most recent tokenize call."""
    return _default_lexer.get_symbol_table()


def print_tokens():
    """Pretty-print the token list from the most recent tokenize call."""
    _default_lexer.print_tokens()


def print_symbol_table():
    """Pretty-print the symbol table from the most recent tokenize call."""
    _default_lexer.print_symbol_table()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        # Demo with inline source
        sample = r"""
#include <stdio.h>

int main(int argc, char *argv[]) {
    int x = 42;
    float pi = 3.14f;
    char *msg = "Hello, World!\n";

    if (argc > 1) {
        x += argc;
    }

    printf("%s x=%d\n", msg, x);
    return 0;
}
"""
        tokens = tokenize_string(sample)
    else:
        tokens = tokenize_file(sys.argv[1])

    print_tokens()
    print_symbol_table()
