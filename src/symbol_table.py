"""
Symbol Table & Scope Management.

Hierarchical scope-based registry of variable and function declarations,
plus the C type-string utilities used by the semantic analyzer.

Scope rules
-----------
* Each :meth:`SymbolTable.enter_scope` pushes a new dictionary onto the scope stack.
* Variable lookup walks the stack innermost → outermost.
* Functions live in a flat global registry (C disallows nested functions).
* A permanent ``_all_vars`` list keeps every variable ever declared, so the
  table can still be inspected after every scope has been popped.

Public API
----------
    VariableEntry, FunctionEntry, ParamInfo  — record dataclasses
    SymbolTable                              — main class
    is_float / is_integral / is_numeric / is_pointer
    promote(a, b)
    compatible(expected, actual)
    type_str(TypeNode)                       — canonical C type string
    STDLIB_BUILTINS                          — known stdlib function names
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .parser import TypeNode


# ─────────────────────────────────────────────────────────────
# Records
# ─────────────────────────────────────────────────────────────

@dataclass
class VariableEntry:
    """A declared variable: name, type, scope level, and source location."""
    name:        str
    type_str:    str    # canonical type, e.g. "int", "char*", "unsigned long"
    scope_level: int    # 0 = global, 1 = function, 2+ = nested block
    line:        int
    column:      int


@dataclass
class ParamInfo:
    """A formal parameter of a function."""
    name:     Optional[str]
    type_str: str


@dataclass
class FunctionEntry:
    """A declared function: signature plus source location."""
    name:        str
    return_type: str
    params:      list[ParamInfo]
    line:        int
    column:      int


# ─────────────────────────────────────────────────────────────
# Symbol table
# ─────────────────────────────────────────────────────────────

class SymbolTable:
    """
    Hierarchical symbol table backed by a scope stack.

    Variables live per-scope (innermost wins on lookup); functions live in
    a flat global registry. Use :meth:`enter_scope` / :meth:`exit_scope`
    to push and pop scopes, :meth:`declare_variable` /
    :meth:`lookup_variable` for variables, and :meth:`declare_function` /
    :meth:`lookup_function` for callables.

    :meth:`all_variables` returns *every* variable ever declared,
    regardless of whether its scope is still active — useful for
    post-analysis reports.
    """

    def __init__(self) -> None:
        self._scopes:    list[dict[str, VariableEntry]] = []
        self._functions: dict[str, FunctionEntry]       = {}
        self._level:     int                            = 0
        self._all_vars:  list[VariableEntry]            = []

    # ── Scope management ───────────────────────────────────────

    def enter_scope(self) -> None:
        """Push a new innermost scope."""
        self._scopes.append({})
        self._level += 1

    def exit_scope(self) -> None:
        """Pop the innermost scope (no-op if no scope is open)."""
        if self._scopes:
            self._scopes.pop()
        self._level = max(0, self._level - 1)

    @property
    def scope_depth(self) -> int:
        """Current scope nesting depth (0 = no scope open)."""
        return self._level

    # ── Variable operations ────────────────────────────────────

    def declare_variable(
        self, name: str, type_str: str, line: int, col: int,
    ) -> Optional[VariableEntry]:
        """
        Register *name* in the innermost scope.

        Returns the existing :class:`VariableEntry` if already declared in
        *this* scope (so the caller can flag a duplicate); otherwise None.
        """
        if not self._scopes:
            return None

        current = self._scopes[-1]
        if name in current:
            return current[name]

        entry = VariableEntry(name, type_str, self._level, line, col)
        current[name] = entry
        self._all_vars.append(entry)
        return None

    def lookup_variable(self, name: str) -> Optional[VariableEntry]:
        """Walk scope stack innermost → outermost; return first match or None."""
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    # ── Function operations ────────────────────────────────────

    def declare_function(
        self,
        name:        str,
        return_type: str,
        params:      list[ParamInfo],
        line:        int,
        col:         int,
    ) -> Optional[FunctionEntry]:
        """Register a function globally. Returns the existing entry on duplicate."""
        if name in self._functions:
            return self._functions[name]
        self._functions[name] = FunctionEntry(name, return_type, params, line, col)
        return None

    def lookup_function(self, name: str) -> Optional[FunctionEntry]:
        """Resolve a function name; return the entry or None."""
        return self._functions.get(name)

    # ── Snapshot helpers (for display / API) ───────────────────

    def all_variables(self) -> list[VariableEntry]:
        """Every variable ever declared, sorted by source line."""
        return sorted(self._all_vars, key=lambda e: e.line)

    def all_functions(self) -> list[FunctionEntry]:
        """Every declared function, sorted by source line."""
        return sorted(self._functions.values(), key=lambda f: f.line)

    def to_dict(self) -> dict:
        """JSON-serializable snapshot of the complete symbol table."""
        return {
            "functions": [
                {
                    "name":        f.name,
                    "return_type": f.return_type,
                    "params":      [
                        {"name": p.name, "type": p.type_str} for p in f.params
                    ],
                    "line":        f.line,
                }
                for f in self.all_functions()
            ],
            "variables": [
                {
                    "name":        v.name,
                    "type":        v.type_str,
                    "scope_level": v.scope_level,
                    "line":        v.line,
                }
                for v in self.all_variables()
            ],
        }

    def print_table(self) -> None:
        """Pretty-print the symbol table for CLI use."""
        print("\n── SYMBOL TABLE ─────────────────────────────────────")
        print("\nFunctions:")
        hdr = f"  {'NAME':<20} {'RETURN':<12} {'PARAMS':<40} LINE"
        print(hdr)
        print("  " + "─" * (len(hdr) - 2))
        for f in self.all_functions():
            params_str = ", ".join(
                f"{p.type_str} {p.name or '?'}" for p in f.params
            ) or "(void)"
            print(f"  {f.name:<20} {f.return_type:<12} {params_str:<40} {f.line}")

        print("\nVariables:")
        hdr2 = f"  {'NAME':<20} {'TYPE':<15} {'SCOPE':<8} LINE"
        print(hdr2)
        print("  " + "─" * (len(hdr2) - 2))
        for v in self.all_variables():
            print(f"  {v.name:<20} {v.type_str:<15} {v.scope_level:<8} {v.line}")
        print()


# ─────────────────────────────────────────────────────────────
# C type utilities
# ─────────────────────────────────────────────────────────────

# Numeric promotion ranks (higher = wider)
_NUMERIC_RANK: dict[str, int] = {
    "char": 0, "short": 1, "int": 2, "unsigned": 2,
    "long": 3, "float": 4, "double": 5,
}
_FLOAT_KEYWORDS = frozenset({"float", "double"})
_INT_KEYWORDS   = frozenset({"char", "short", "int", "unsigned", "signed", "long"})

# Standard-library functions whose declarations we don't require in source.
STDLIB_BUILTINS = frozenset({
    "printf", "fprintf", "sprintf", "snprintf",
    "scanf",  "fscanf",  "sscanf",
    "puts",   "gets",    "fgets", "fputs",
    "fopen",  "fclose",  "fread", "fwrite", "fseek", "ftell", "rewind",
    "malloc", "calloc",  "realloc", "free",
    "strlen", "strcpy",  "strncpy", "strcat", "strncat", "strcmp", "strncmp",
    "memcpy", "memmove", "memset", "memcmp",
    "atoi",   "atof",    "atol",
    "abs",    "fabs",    "sqrt",  "pow",  "sin",  "cos",  "tan",
    "ceil",   "floor",   "round",
    "exit",   "abort",   "atexit",
    "assert",
    "time",   "clock",   "difftime",
    "rand",   "srand",
})


def type_str(node: TypeNode) -> str:
    """Convert a :class:`TypeNode` to a canonical string ('int', 'char*', …)."""
    return node.base + "*" * node.pointer_depth


def is_float(t: str) -> bool:
    """True if *t* names a floating-point type."""
    base = t.rstrip("*").strip()
    return any(w in _FLOAT_KEYWORDS for w in base.split())


def is_integral(t: str) -> bool:
    """True if *t* names a non-floating numeric (int/char/long/short/...)."""
    base = t.rstrip("*").strip()
    return (
        not is_float(t)
        and any(w in _INT_KEYWORDS for w in base.split())
    )


def is_numeric(t: str) -> bool:
    """True if *t* is any numeric type."""
    return is_float(t) or is_integral(t)


def is_pointer(t: str) -> bool:
    """True if *t* contains a pointer star."""
    return "*" in t


def promote(a: str, b: str) -> str:
    """Result type when combining types *a* and *b* (simplified C rules)."""
    a_words = a.rstrip("*").strip().split()
    b_words = b.rstrip("*").strip().split()
    a_rank = max((_NUMERIC_RANK.get(w, -1) for w in a_words), default=-1)
    b_rank = max((_NUMERIC_RANK.get(w, -1) for w in b_words), default=-1)
    if a_rank == -1 or b_rank == -1:
        return "int"
    return a.rstrip("*").strip() if a_rank >= b_rank else b.rstrip("*").strip()


def compatible(expected: str, actual: str) -> bool:
    """
    True if assigning a value of type *actual* to a target of type
    *expected* is allowed (with possible numeric narrowing).
    """
    if expected == actual:
        return True
    if "unknown" in (expected, actual):
        return True

    e_ptr = expected.count("*")
    a_ptr = actual.count("*")

    if e_ptr != a_ptr:
        # Allow integer literal 0 as a null pointer.
        if a_ptr == 0 and actual == "int" and e_ptr > 0:
            return True
        return False

    if is_numeric(expected) and is_numeric(actual):
        return True

    return False
