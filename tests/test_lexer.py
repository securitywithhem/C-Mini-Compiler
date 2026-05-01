"""
Unit tests for the lexer (Phase 1).

Verifies that the tokenizer:
  * Recognizes all token categories (keyword, identifier, literal, operator,
    separator, comment, preprocessor)
  * Skips whitespace correctly
  * Tracks line and column accurately
  * Builds the symbol table for identifiers
"""

from __future__ import annotations

import sys

from src.lexer import (
    C_KEYWORDS,
    Lexer,
    Token,
    TokenType,
    tokenize_string,
)

_PASS = 0
_FAIL = 0


def _check(label: str, ok: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    status = "\033[32mPASS\033[0m" if ok else "\033[31mFAIL\033[0m"
    print(f"  [{status}] {label}")
    if not ok and detail:
        print(f"           ↳ {detail}")
    _PASS += int(bool(ok))
    _FAIL += int(not ok)


def _types(tokens: list[Token]) -> list[TokenType]:
    return [t.type for t in tokens]


def _values(tokens: list[Token]) -> list[str]:
    return [t.value for t in tokens]


# ═════════════════════════════════════════════════════════════
# 1. Basic token recognition
# ═════════════════════════════════════════════════════════════
print("\n── 1. TOKEN RECOGNITION ────────────────────────────────")

tokens = tokenize_string("int x = 42;")
_check(
    "simple declaration → 5 tokens",
    len(tokens) == 5,
    f"got {len(tokens)} tokens: {_values(tokens)}",
)
_check(
    "first token is KEYWORD 'int'",
    tokens[0].type is TokenType.KEYWORD and tokens[0].value == "int",
)
_check(
    "second token is IDENTIFIER 'x'",
    tokens[1].type is TokenType.IDENTIFIER and tokens[1].value == "x",
)
_check(
    "third token is OPERATOR '='",
    tokens[2].type is TokenType.OPERATOR and tokens[2].value == "=",
)
_check(
    "fourth token is INTEGER '42'",
    tokens[3].type is TokenType.INTEGER and tokens[3].value == "42",
)
_check(
    "fifth token is SEPARATOR ';'",
    tokens[4].type is TokenType.SEPARATOR and tokens[4].value == ";",
)

# ═════════════════════════════════════════════════════════════
# 2. Keyword vs identifier
# ═════════════════════════════════════════════════════════════
print("\n── 2. KEYWORDS VS IDENTIFIERS ──────────────────────────")

for kw in ("int", "float", "void", "if", "for", "while", "return", "char"):
    t = tokenize_string(kw + ";")[0]
    _check(f"'{kw}' is recognized as KEYWORD", t.type is TokenType.KEYWORD)

for ident in ("x", "myVar", "_underscore", "var123"):
    t = tokenize_string(f"int {ident};")[1]
    _check(f"'{ident}' is recognized as IDENTIFIER", t.type is TokenType.IDENTIFIER)

_check(
    "C_KEYWORDS contains 'int', 'return', 'while'",
    {"int", "return", "while"}.issubset(C_KEYWORDS),
)

# ═════════════════════════════════════════════════════════════
# 3. Numeric literals
# ═════════════════════════════════════════════════════════════
print("\n── 3. NUMERIC LITERALS ─────────────────────────────────")

cases = [
    ("42",      TokenType.INTEGER),
    ("0",       TokenType.INTEGER),
    ("0xFF",    TokenType.INTEGER),
    ("0777",    TokenType.INTEGER),
    ("100u",    TokenType.INTEGER),
    ("3.14",    TokenType.FLOAT),
    ("3.14f",   TokenType.FLOAT),
    ("1.5e-2",  TokenType.FLOAT),
    ("0.5",     TokenType.FLOAT),
]
for src, expected in cases:
    toks = tokenize_string(src + ";")
    _check(
        f"'{src}' → {expected.name}",
        toks[0].type is expected,
        f"got {toks[0].type.name}",
    )

# ═════════════════════════════════════════════════════════════
# 4. Operators (incl. multi-char)
# ═════════════════════════════════════════════════════════════
print("\n── 4. OPERATORS ────────────────────────────────────────")

multi_char = ["==", "!=", "<=", ">=", "&&", "||", "<<", ">>", "++", "--",
              "+=", "-=", "*=", "/=", "->"]
for op in multi_char:
    toks = tokenize_string(f"a {op} b;")
    op_token = next((t for t in toks if t.type is TokenType.OPERATOR), None)
    _check(
        f"multi-char operator '{op}' kept intact",
        op_token is not None and op_token.value == op,
        f"tokens: {_values(toks)}",
    )

# ═════════════════════════════════════════════════════════════
# 5. String and character literals
# ═════════════════════════════════════════════════════════════
print("\n── 5. STRING / CHAR LITERALS ───────────────────────────")

t = tokenize_string('"hello world";')[0]
_check("string literal type", t.type is TokenType.STRING)
_check("string literal preserves quotes", t.value == '"hello world"')

t = tokenize_string("'a';")[0]
_check("char literal type", t.type is TokenType.CHAR)

t = tokenize_string(r'"with\nescape";')[0]
_check("string with escape sequence", t.type is TokenType.STRING)

# ═════════════════════════════════════════════════════════════
# 6. Comments and whitespace skipped
# ═════════════════════════════════════════════════════════════
print("\n── 6. COMMENTS & WHITESPACE ────────────────────────────")

src = """
// line comment
int x = 1;       // trailing comment
/* block
   comment */
int y = 2;
"""
toks = tokenize_string(src)
no_comments = all(t.type is not TokenType.COMMENT for t in toks)
_check("comments stripped from token stream", no_comments)
identifiers = [t for t in toks if t.type is TokenType.IDENTIFIER]
_check(
    "exactly two identifiers (x, y) remain",
    [t.value for t in identifiers] == ["x", "y"],
)

# ═════════════════════════════════════════════════════════════
# 7. Line and column tracking
# ═════════════════════════════════════════════════════════════
print("\n── 7. LINE/COLUMN TRACKING ─────────────────────────────")

src = "int x;\nfloat y;"
toks = tokenize_string(src)
_check(
    "first token on line 1",
    toks[0].line == 1,
    f"got line {toks[0].line}",
)
float_tok = next(t for t in toks if t.value == "float")
_check(
    "'float' on line 2",
    float_tok.line == 2,
    f"got line {float_tok.line}",
)
_check(
    "first column of 'int' is 1",
    toks[0].column == 1,
    f"got col {toks[0].column}",
)

# ═════════════════════════════════════════════════════════════
# 8. Symbol table
# ═════════════════════════════════════════════════════════════
print("\n── 8. SYMBOL TABLE ─────────────────────────────────────")

lex = Lexer()
lex.tokenize("int x = 5; x = x + 1; int y = x;")
table = lex.get_symbol_table()
_check("symbol table contains 'x'", "x" in table)
_check("symbol table contains 'y'", "y" in table)
_check(
    "'x' has multiple occurrences",
    len(table["x"].occurrences) >= 3,
    f"got {len(table.get('x').occurrences) if 'x' in table else 0}",
)

# ═════════════════════════════════════════════════════════════
# 9. Preprocessor directives
# ═════════════════════════════════════════════════════════════
print("\n── 9. PREPROCESSOR ─────────────────────────────────────")

toks = tokenize_string("#include <stdio.h>\nint main() {}")
preproc = [t for t in toks if t.type is TokenType.PREPROCESSOR]
_check(
    "#include is preserved as PREPROCESSOR token",
    len(preproc) == 1 and "#include" in preproc[0].value,
)

# ═════════════════════════════════════════════════════════════
# 10. Edge cases: empty / whitespace-only
# ═════════════════════════════════════════════════════════════
print("\n── 10. EDGE CASES ──────────────────────────────────────")

_check("empty input → no tokens", tokenize_string("") == [])
_check("whitespace-only → no tokens", tokenize_string("   \n\t  ") == [])
_check("comments-only → no tokens", tokenize_string("/* hello */\n// world") == [])

# ═════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════

total = _PASS + _FAIL
print(f"""
══════════════════════════════════════════════════════════
  Lexer tests:  {_PASS}/{total} passed   ({_FAIL} failed)
══════════════════════════════════════════════════════════
""")

sys.exit(0 if _FAIL == 0 else 1)
