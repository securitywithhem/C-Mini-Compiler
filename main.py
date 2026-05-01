#!/usr/bin/env python3
"""
C Mini-Compiler — command-line entry point.

Usage
-----
    python main.py [OPTIONS] FILE

Options
-------
    --format FMT     Output format: console (default) | plain | json | summary
    --no-color       Disable ANSI color codes
    -h, --help       Show help

Exit codes
----------
    0  no errors  (warnings allowed)
    1  at least one error
    2  bad usage / file not found
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from src.compiler import compile_file


_USAGE = __doc__ or ""

_VALID_FORMATS = {"console", "plain", "json", "summary"}


def main(argv: Optional[list[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    fmt   = "console"
    color = True
    file_arg: Optional[str] = None

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
            sys.stderr.write(f"error: unknown option {a!r}\n{_USAGE}")
            return 2
        else:
            if file_arg is not None:
                sys.stderr.write("error: only one FILE may be given\n")
                return 2
            file_arg = a
        i += 1

    if file_arg is None:
        sys.stderr.write(_USAGE)
        return 2
    if fmt not in _VALID_FORMATS:
        sys.stderr.write(
            f"error: invalid format {fmt!r}; choose from {sorted(_VALID_FORMATS)}\n"
        )
        return 2
    if not Path(file_arg).is_file():
        sys.stderr.write(f"error: file not found: {file_arg}\n")
        return 2

    text, code = compile_file(file_arg, fmt=fmt, color=color)
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
