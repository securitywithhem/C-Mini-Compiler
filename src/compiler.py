"""
Driver / orchestrator for the C Mini-Compiler pipeline.

Composes lexer → parser → validator → semantic → reporter into single
high-level entry points so callers don't have to wire phases together
manually.

    >>> from src.compiler import compile_source
    >>> text, exit_code = compile_source(open("file.c").read())
    >>> print(text)

For a CLI front-end, see :mod:`main` at the project root.
"""

from __future__ import annotations

from typing import Optional

from .error_handler import (
    UnifiedError,
    collect_errors,
    report_string,
    report_file,
)
from .symbol_table import SymbolTable


def compile_source(
    source:    str,
    *,
    fmt:       str  = "console",
    color:     bool = True,
    file_name: Optional[str] = None,
) -> tuple[str, int]:
    """
    Run every phase on *source* and return ``(formatted_report, exit_code)``.

    Exit codes
        0  no errors  (warnings allowed)
        1  at least one hard error
    """
    return report_string(source, fmt=fmt, color=color, file_name=file_name)


def compile_file(
    filename: str,
    *,
    fmt:      str  = "console",
    color:    bool = True,
) -> tuple[str, int]:
    """Read *filename*, run the full pipeline, return ``(text, exit_code)``."""
    return report_file(filename, fmt=fmt, color=color)


def collect(source: str) -> tuple[list[UnifiedError], SymbolTable]:
    """Run every phase and return raw ``(errors, symbol_table)`` for programmatic use."""
    return collect_errors(source)


__all__ = ["compile_source", "compile_file", "collect"]
