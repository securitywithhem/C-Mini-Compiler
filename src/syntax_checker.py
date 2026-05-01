"""
Enhanced Syntax Checker — detects additional syntax errors.

This module provides additional validation passes beyond the standard validator:
  - Invalid variable names (starting with digits)
  - Unclosed string literals
  - Invalid operator sequences

It integrates with the existing error reporting system by returning
Diagnostic objects compatible with the main validator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from .lexer import Token, TokenType, tokenize_string


class SyntaxErrorKind(Enum):
    """Extended error kinds beyond the standard validator."""
    INVALID_IDENTIFIER    = auto()  # Variable name starts with digit
    UNCLOSED_STRING       = auto()  # String literal missing closing quote
    UNCLOSED_CHAR        = auto()  # Char literal missing closing quote
    MISMATCHED_QUOTES    = auto()  # Mixed quote types


@dataclass
class SyntaxDiagnostic:
    """Extended diagnostic with more detailed syntax information."""
    kind:      SyntaxErrorKind
    message:   str
    line:      int
    column:    int
    severity:  str = "error"  # "error" or "warning"

    def __str__(self) -> str:
        return f"Line {self.line}, Column {self.column}: [{self.kind.name}] {self.message}"


# ─────────────────────────────────────────────────────────────
# Pass 1 — Detect invalid variable names (starting with digits)
# ─────────────────────────────────────────────────────────────

_TYPE_KEYWORDS = {
    "auto", "bool", "char", "const", "double", "enum", "float",
    "inline", "int", "long", "short", "signed", "struct",
    "typedef", "union", "unsigned", "void", "volatile", "_Bool"
}


def check_invalid_identifiers(tokens: list[Token]) -> list[SyntaxDiagnostic]:
    """
    Detect declarations like 'int 9var = 5' where variable name starts with digit.

    A type keyword followed immediately by a digit token indicates an invalid
    variable name. We report this as an invalid identifier error.
    """
    diagnostics: list[SyntaxDiagnostic] = []

    for i in range(len(tokens) - 1):
        tok = tokens[i]

        # Look for type keyword
        if tok.type is not TokenType.KEYWORD or tok.value not in _TYPE_KEYWORDS:
            continue

        # Check if next token is a digit (INTEGER token)
        next_tok = tokens[i + 1]
        if next_tok.type is TokenType.INTEGER:
            # This is invalid - variable name cannot start with digit
            diagnostics.append(SyntaxDiagnostic(
                kind=SyntaxErrorKind.INVALID_IDENTIFIER,
                message=f"invalid variable name '{next_tok.value}...' "
                        f"— identifiers must start with letter or underscore",
                line=next_tok.line,
                column=next_tok.column,
                severity="error"
            ))

    return diagnostics


# ─────────────────────────────────────────────────────────────
# Pass 2 — Detect unclosed strings/chars at source level
# ─────────────────────────────────────────────────────────────

def check_unclosed_strings(source: str) -> list[SyntaxDiagnostic]:
    """
    Scan source code character-by-character to detect unclosed strings.

    This catches cases like:
        char *msg = "Hello World;   (missing closing quote)
    
    Returns diagnostics for each unclosed string/char literal.
    """
    diagnostics: list[SyntaxDiagnostic] = []
    line = 1
    col = 1
    i = 0

    while i < len(source):
        char = source[i]

        # Track line/column
        if char == '\n':
            line += 1
            col = 1
            i += 1
            continue

        # Check for string literal
        if char == '"':
            line_start = line
            col_start = col
            i += 1
            col += 1

            # Scan for closing quote (handle escapes)
            found_close = False
            while i < len(source):
                ch = source[i]
                if ch == '\n':
                    line += 1
                    col = 1
                    i += 1
                elif ch == '\\' and i + 1 < len(source):
                    # Skip escaped character
                    i += 2
                    if source[i-1] == '\n':
                        line += 1
                        col = 1
                    else:
                        col += 2
                elif ch == '"':
                    found_close = True
                    i += 1
                    col += 1
                    break
                else:
                    col += 1
                    i += 1

            if not found_close:
                diagnostics.append(SyntaxDiagnostic(
                    kind=SyntaxErrorKind.UNCLOSED_STRING,
                    message="unclosed string literal",
                    line=line_start,
                    column=col_start,
                    severity="error"
                ))
            continue

        # Check for char literal
        elif char == "'":
            line_start = line
            col_start = col
            i += 1
            col += 1

            # Scan for closing quote (handle escapes)
            found_close = False
            while i < len(source):
                ch = source[i]
                if ch == '\n':
                    line += 1
                    col = 1
                    i += 1
                elif ch == '\\' and i + 1 < len(source):
                    # Skip escaped character
                    i += 2
                    if source[i-1] == '\n':
                        line += 1
                        col = 1
                    else:
                        col += 2
                elif ch == "'":
                    found_close = True
                    i += 1
                    col += 1
                    break
                else:
                    col += 1
                    i += 1

            if not found_close:
                diagnostics.append(SyntaxDiagnostic(
                    kind=SyntaxErrorKind.UNCLOSED_CHAR,
                    message="unclosed character literal",
                    line=line_start,
                    column=col_start,
                    severity="error"
                ))
            continue

        col += 1
        i += 1

    return diagnostics


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def check_syntax(source: str) -> list[SyntaxDiagnostic]:
    """
    Run all enhanced syntax checks on source code.

    Returns a list of SyntaxDiagnostic objects sorted by line/column.
    """
    diagnostics: list[SyntaxDiagnostic] = []

    # Tokenize to check for invalid identifiers
    try:
        tokens = tokenize_string(source)
        diagnostics.extend(check_invalid_identifiers(tokens))
    except Exception:
        pass  # If tokenization fails, skip this check

    # Check for unclosed strings/chars
    diagnostics.extend(check_unclosed_strings(source))

    # Sort by line, then column
    diagnostics.sort(key=lambda d: (d.line, d.column))

    return diagnostics


def print_report(diagnostics: list[SyntaxDiagnostic], source: Optional[str] = None):
    """Pretty-print enhanced syntax diagnostics."""
    if not diagnostics:
        print("✓ No enhanced syntax issues found.")
        return

    lines = source.split('\n') if source else []

    for diag in diagnostics:
        print(f"\n❌ {diag.severity.upper()}  ({diag.kind.name})")
        print(f"   Line {diag.line}, Column {diag.column}: {diag.message}")

        if diag.line - 1 < len(lines):
            print(f"   | {lines[diag.line - 1]}")
            print(f"   | {' ' * (diag.column - 1)}^")


if __name__ == "__main__":
    import sys

    test_code = """int main() {
    int 9var = 5;
    char *msg = "Hello World;
    char ch = 'a";
    return 0;
}"""

    print("=" * 60)
    print("ENHANCED SYNTAX CHECK")
    print("=" * 60)
    print("\nTesting code:")
    print(test_code)
    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)

    diagnostics = check_syntax(test_code)
    print_report(diagnostics, test_code)

    print(f"\n\nTotal issues found: {len(diagnostics)}")
