"""
Phase 5 — Unified Error Reporting

Aggregates diagnostics from every earlier phase into a single, sorted,
nicely formatted report with multiple output formats.

Sources of errors
-----------------
  Phase 1-3  (c_validator)  — syntax: missing-semicolon, unmatched-brace,
                              invalid-assign, missing-return, unexpected-token
  Phase 4    (c_semantic)   — semantic: undeclared-variable, divide-by-zero,
                              argument-mismatch, multiple-declaration,
                              undeclared-function, type-mismatch (warning)

Public API
----------
  collect_errors(source)              -> list[UnifiedError]
  report_string(source, fmt='console')-> tuple[str, int]   # (text, exit_code)
  report_file(filename, ...)          -> tuple[str, int]
  main()                              -> CLI entry point
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from typing import Optional

from .validator    import validate_string, ErrorKind   as SyntaxKind
from .semantic     import analyze_string, SemanticErrorKind
from .symbol_table import SymbolTable


# ─────────────────────────────────────────────────────────────
# Unified error model
# ─────────────────────────────────────────────────────────────

# Map every kind name → human-readable category label
_CATEGORY: dict[str, str] = {
    # Syntax (Phase 1-3)
    "MISSING_SEMICOLON":    "Syntax — Missing Semicolon",
    "UNMATCHED_BRACE":      "Syntax — Unmatched Brace",
    "INVALID_ASSIGN":       "Syntax — Invalid Assignment",
    "MISSING_RETURN":       "Syntax — Missing Return",
    "UNEXPECTED_TOKEN":     "Syntax — Unexpected Token",
    # Semantic (Phase 4)
    "UNDECLARED_VARIABLE":  "Semantic — Undeclared Variable",
    "DIVIDE_BY_ZERO":       "Semantic — Invalid Operation",
    "ARGUMENT_MISMATCH":    "Semantic — Function Argument Mismatch",
    "MULTIPLE_DECLARATION": "Semantic — Multiple Declaration",
    "UNDECLARED_FUNCTION":  "Semantic — Undeclared Function",
    "TYPE_MISMATCH":        "Semantic — Type Mismatch",
}


@dataclass
class UnifiedError:
    phase:    str   # "syntax" | "semantic"
    kind:     str   # e.g. "MISSING_SEMICOLON"
    category: str   # e.g. "Syntax — Missing Semicolon"
    message:  str
    line:     int
    column:   int
    severity: str   # "error" | "warning"

    def short(self) -> str:
        """One-line human summary: 'Line X, Column Y: [KIND] message'."""
        return f"Line {self.line}, Column {self.column}: [{self.kind}] {self.message}"


# ─────────────────────────────────────────────────────────────
# Collection
# ─────────────────────────────────────────────────────────────

def collect_errors(source: str) -> tuple[list[UnifiedError], SymbolTable]:
    """Run all phases and return a sorted list of unified errors."""
    out: list[UnifiedError] = []

    # Phase 1-3: syntax
    for d in validate_string(source):
        kind_name = d.kind.name
        out.append(UnifiedError(
            phase    = "syntax",
            kind     = kind_name,
            category = _CATEGORY.get(kind_name, kind_name),
            message  = d.message,
            line     = d.line,
            column   = d.column,
            severity = "error",
        ))

    # Phase 4: semantic
    sem_errors, table = analyze_string(source)
    for e in sem_errors:
        kind_name = e.kind.name
        out.append(UnifiedError(
            phase    = "semantic",
            kind     = kind_name,
            category = _CATEGORY.get(kind_name, kind_name),
            message  = e.message,
            line     = e.line,
            column   = e.column,
            severity = "warning" if e.is_warning else "error",
        ))

    out.sort(key=lambda e: (e.line, e.column, 0 if e.phase == "syntax" else 1))
    return out, table


# ─────────────────────────────────────────────────────────────
# Output formatters
# ─────────────────────────────────────────────────────────────

# ANSI color helpers
class _C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"


def _strip(s: str) -> str:
    """Strip ANSI escape codes (used when color is disabled)."""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "\033" and i + 1 < n and s[i + 1] == "[":
            j = s.find("m", i)
            if j == -1:
                break
            i = j + 1
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _format_console(
    errors:    list[UnifiedError],
    source:    str,
    *,
    color:     bool = True,
    file_name: Optional[str] = None,
) -> str:
    """Rich console output with source-line context and caret pointers."""
    src_lines = source.splitlines()
    lines: list[str] = []

    # Header
    header = "── COMPILATION REPORT "
    if file_name:
        header += f"({file_name}) "
    header += "─" * max(0, 60 - len(header))
    lines.append(f"{_C.BOLD}{header}{_C.RESET}")

    if not errors:
        lines.append(f"{_C.BOLD}{_C.GREEN}✓ No errors. Compilation successful.{_C.RESET}")
        out = "\n".join(lines) + "\n"
        return out if color else _strip(out)

    # Error list with source context
    for e in errors:
        marker  = "❌" if e.severity == "error" else "⚠️ "
        sev_col = _C.RED if e.severity == "error" else _C.YELLOW
        lines.append("")
        lines.append(
            f"{marker} {_C.BOLD}{sev_col}{e.severity.upper()}{_C.RESET}  "
            f"{_C.DIM}({e.category}){_C.RESET}"
        )
        lines.append(
            f"   Line {_C.BOLD}{e.line}{_C.RESET}, "
            f"Column {_C.BOLD}{e.column}{_C.RESET}: "
            f"[{_C.CYAN}{e.kind}{_C.RESET}]"
        )
        lines.append(f"   {e.message}")
        if 1 <= e.line <= len(src_lines):
            src = src_lines[e.line - 1]
            lines.append(f"   {_C.DIM}|{_C.RESET} {src}")
            if e.column > 0:
                pad = " " * (e.column - 1)
                lines.append(f"   {_C.DIM}|{_C.RESET} {pad}{sev_col}^{_C.RESET}")

    # Summary
    lines.append("")
    lines.append("─" * 60)
    n_err  = sum(1 for e in errors if e.severity == "error")
    n_warn = sum(1 for e in errors if e.severity == "warning")

    by_cat: dict[str, int] = {}
    for e in errors:
        by_cat[e.category] = by_cat.get(e.category, 0) + 1

    lines.append(
        f"{_C.BOLD}Summary:{_C.RESET} "
        f"{_C.RED}{n_err} error(s){_C.RESET}, "
        f"{_C.YELLOW}{n_warn} warning(s){_C.RESET}"
    )
    for cat, count in sorted(by_cat.items()):
        lines.append(f"  • {cat}: {count}")

    out = "\n".join(lines) + "\n"
    return out if color else _strip(out)


def _format_plain(
    errors:    list[UnifiedError],
    source:    str,
    *,
    file_name: Optional[str] = None,
) -> str:
    """Compact plain-text format — one line per error."""
    if not errors:
        return "OK: no errors\n"

    lines = []
    if file_name:
        lines.append(f"File: {file_name}")
    for e in errors:
        tag = "error" if e.severity == "error" else "warning"
        lines.append(
            f"{file_name + ':' if file_name else ''}"
            f"{e.line}:{e.column}: {tag}: [{e.kind}] {e.message}"
        )
    n_err  = sum(1 for e in errors if e.severity == "error")
    n_warn = sum(1 for e in errors if e.severity == "warning")
    lines.append(f"Total: {n_err} error(s), {n_warn} warning(s)")
    return "\n".join(lines) + "\n"


def _format_json(
    errors:       list[UnifiedError],
    symbol_table: SymbolTable,
    *,
    file_name:    Optional[str] = None,
) -> str:
    """Machine-readable JSON output."""
    payload = {
        "file":         file_name,
        "errors":       [asdict(e) for e in errors],
        "symbol_table": symbol_table.to_dict(),
        "summary": {
            "errors":   sum(1 for e in errors if e.severity == "error"),
            "warnings": sum(1 for e in errors if e.severity == "warning"),
            "by_category": {
                cat: sum(1 for e in errors if e.category == cat)
                for cat in {e.category for e in errors}
            },
        },
    }
    return json.dumps(payload, indent=2) + "\n"


def _format_summary(
    errors:    list[UnifiedError],
    source:    str,
    *,
    color:     bool = True,
    file_name: Optional[str] = None,
) -> str:
    """Counts-only summary — no per-error details."""
    if not errors:
        msg = f"{_C.BOLD}{_C.GREEN}✓ No errors{_C.RESET}\n"
        return msg if color else _strip(msg)

    n_err  = sum(1 for e in errors if e.severity == "error")
    n_warn = sum(1 for e in errors if e.severity == "warning")

    lines = [
        f"{_C.BOLD}Compilation summary"
        f"{(' for ' + file_name) if file_name else ''}:{_C.RESET}",
        f"  {_C.RED}{n_err} error(s){_C.RESET}",
        f"  {_C.YELLOW}{n_warn} warning(s){_C.RESET}",
        "",
    ]
    by_cat: dict[str, int] = {}
    for e in errors:
        by_cat[e.category] = by_cat.get(e.category, 0) + 1
    for cat, c in sorted(by_cat.items()):
        lines.append(f"  • {cat}: {c}")

    out = "\n".join(lines) + "\n"
    return out if color else _strip(out)


# ─────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────

_FORMATTERS = {"console", "plain", "json", "summary"}


def report_string(
    source:    str,
    *,
    fmt:       str  = "console",
    color:     bool = True,
    file_name: Optional[str] = None,
) -> tuple[str, int]:
    """
    Run all phases on *source* and return ``(formatted_text, exit_code)``.

    Exit code: 0 = no errors (warnings allowed), 1 = at least one error.
    """
    if fmt not in _FORMATTERS:
        raise ValueError(f"unknown format {fmt!r}, expected one of {_FORMATTERS}")

    errors, table = collect_errors(source)

    if fmt == "console":
        text = _format_console(errors, source, color=color, file_name=file_name)
    elif fmt == "plain":
        text = _format_plain(errors, source, file_name=file_name)
    elif fmt == "json":
        text = _format_json(errors, table, file_name=file_name)
    else:  # summary
        text = _format_summary(errors, source, color=color, file_name=file_name)

    exit_code = 1 if any(e.severity == "error" for e in errors) else 0
    return text, exit_code


def report_file(
    filename: str,
    *,
    fmt:      str  = "console",
    color:    bool = True,
) -> tuple[str, int]:
    """Read *filename*, run the report, return ``(text, exit_code)``."""
    with open(filename, encoding="utf-8", errors="replace") as fh:
        source = fh.read()
    return report_string(source, fmt=fmt, color=color, file_name=filename)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

_USAGE = """\
Usage: python c_reporter.py [OPTIONS] FILE

Validate a C source file and print a unified error report.

Options:
  --format FMT     Output format: console (default) | plain | json | summary
  --no-color       Disable ANSI color codes
  -h, --help       Show this help

Exit codes:
  0  no errors (warnings allowed)
  1  at least one error
  2  bad usage / file not found
"""


def main(argv: Optional[list[str]] = None) -> int:
    args = (argv if argv is not None else sys.argv[1:])
    fmt: str = "console"
    color: bool = True
    file: Optional[str] = None

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help"):
            sys.stdout.write(_USAGE)
            return 0
        if a == "--format":
            i += 1
            if i >= len(args):
                sys.stderr.write("error: --format requires a value\n")
                return 2
            fmt = args[i]
        elif a.startswith("--format="):
            fmt = a.split("=", 1)[1]
        elif a == "--no-color":
            color = False
        elif a.startswith("-"):
            sys.stderr.write(f"error: unknown option {a}\n")
            sys.stderr.write(_USAGE)
            return 2
        else:
            if file is not None:
                sys.stderr.write("error: only one FILE may be specified\n")
                return 2
            file = a
        i += 1

    if file is None:
        sys.stderr.write(_USAGE)
        return 2

    if fmt not in _FORMATTERS:
        sys.stderr.write(
            f"error: invalid format {fmt!r}; choose from {sorted(_FORMATTERS)}\n"
        )
        return 2

    try:
        text, code = report_file(file, fmt=fmt, color=color)
    except FileNotFoundError:
        sys.stderr.write(f"error: file not found: {file}\n")
        return 2

    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
