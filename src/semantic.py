"""
Phase 4 — Semantic Analysis

Walks the AST built by :mod:`src.parser` and detects errors beyond syntax.

Detected error types
--------------------
==========================  =====================================================
``UNDECLARED_VARIABLE``     Variable used before declaration in any enclosing scope
``DIVIDE_BY_ZERO``          Division/modulo by integer literal 0
``ARGUMENT_MISMATCH``       Wrong number of arguments passed to a function
``MULTIPLE_DECLARATION``    Same variable declared twice in the same scope
``UNDECLARED_FUNCTION``     Call to a function not declared in the translation unit
``TYPE_MISMATCH``           Incompatible types in assignment or call (warning)
==========================  =====================================================

Public API
----------
    analyze_string(source)            -> (list[SemanticError], SymbolTable)
    analyze_file(filename)            -> (list[SemanticError], SymbolTable)
    analyze_ast(ast: ProgramNode)     -> (list[SemanticError], SymbolTable)
    print_report(errors, source)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from .lexer import tokenize_file, tokenize_string
from .parser import (
    ASTNode, AssignNode, BinaryOpNode, BlockNode, CallNode,
    CharLiteralNode, FloatLiteralNode, ForNode, FuncDeclNode,
    IdentifierNode, IfNode, IndexNode, IntLiteralNode, JumpNode,
    ParamNode, PostfixOpNode, ProgramNode, ReturnNode,
    StringLiteralNode, TernaryNode, TypeNode, UnaryOpNode,
    VarDeclarator, VarDeclNode, WhileNode, ExprStmtNode,
    Visitor,
    parse_file as _parse_file,
    parse_string as _parse_string,
)
from .symbol_table import (
    FunctionEntry, ParamInfo, SymbolTable,
    STDLIB_BUILTINS,
    type_str as _type_str,
    is_float, is_integral,
    promote, compatible,
)


# ─────────────────────────────────────────────────────────────
# Error model
# ─────────────────────────────────────────────────────────────

class SemanticErrorKind(Enum):
    """All semantic error categories detected by :class:`SemanticAnalyzer`."""
    UNDECLARED_VARIABLE  = auto()
    DIVIDE_BY_ZERO       = auto()
    ARGUMENT_MISMATCH    = auto()
    MULTIPLE_DECLARATION = auto()
    UNDECLARED_FUNCTION  = auto()
    TYPE_MISMATCH        = auto()   # reported as warning


_KIND_LABEL: dict[SemanticErrorKind, str] = {
    SemanticErrorKind.UNDECLARED_VARIABLE:  "undeclared variable",
    SemanticErrorKind.DIVIDE_BY_ZERO:       "divide by zero",
    SemanticErrorKind.ARGUMENT_MISMATCH:    "argument mismatch",
    SemanticErrorKind.MULTIPLE_DECLARATION: "multiple declaration",
    SemanticErrorKind.UNDECLARED_FUNCTION:  "undeclared function",
    SemanticErrorKind.TYPE_MISMATCH:        "type mismatch",
}


@dataclass
class SemanticError:
    """A single semantic diagnostic."""
    kind:       SemanticErrorKind
    message:    str
    line:       int
    column:     int
    is_warning: bool = False

    def __str__(self) -> str:
        severity = "WARNING" if self.is_warning else "ERROR"
        label    = _KIND_LABEL[self.kind].upper()
        return (
            f"[{label}] {severity}  "
            f"line {self.line}, col {self.column}  — {self.message}"
        )


# ─────────────────────────────────────────────────────────────
# Semantic analyzer (AST visitor)
# ─────────────────────────────────────────────────────────────

class SemanticAnalyzer(Visitor):
    """
    Two-pass AST visitor that builds a :class:`SymbolTable` and collects
    :class:`SemanticError` instances.

    Pass 1 (pre-scan)
        Register every top-level function signature so that calls to a
        function defined later in the file still resolve correctly.

    Pass 2 (full walk)
        Resolve every identifier, type-check expressions, validate calls,
        detect duplicate declarations, flag divide-by-zero, etc.
    """

    def __init__(self) -> None:
        self.errors:        list[SemanticError]      = []
        self.symbol_table:  SymbolTable              = SymbolTable()
        self._current_func: Optional[FunctionEntry]  = None

    # ── Error helpers ──────────────────────────────────────────

    def _err(
        self,
        kind:    SemanticErrorKind,
        msg:     str,
        line:    int,
        col:     int = 0,
        warning: bool = False,
    ) -> None:
        self.errors.append(SemanticError(kind, msg, line, col, warning))

    # ── Type inference ─────────────────────────────────────────

    def _infer(self, node: ASTNode) -> str:
        """Best-effort type inference for an expression node."""
        if isinstance(node, IntLiteralNode):
            return "int"
        if isinstance(node, FloatLiteralNode):
            return "float"
        if isinstance(node, StringLiteralNode):
            return "char*"
        if isinstance(node, CharLiteralNode):
            return "char"
        if isinstance(node, IdentifierNode):
            entry = self.symbol_table.lookup_variable(node.name)
            return entry.type_str if entry else "unknown"
        if isinstance(node, BinaryOpNode):
            if node.op in ("==", "!=", "<", ">", "<=", ">=", "&&", "||"):
                return "int"
            return promote(self._infer(node.left), self._infer(node.right))
        if isinstance(node, UnaryOpNode):
            if node.op in ("!", "~"):
                return "int"
            if node.op == "&":
                return self._infer(node.operand) + "*"
            if node.op == "*":
                t = self._infer(node.operand)
                return t.rstrip("*") if t.endswith("*") else "unknown"
            return self._infer(node.operand)
        if isinstance(node, AssignNode):
            return self._infer(node.value)
        if isinstance(node, TernaryNode):
            return promote(self._infer(node.then_expr), self._infer(node.else_expr))
        if isinstance(node, CallNode):
            fn = self.symbol_table.lookup_function(node.callee)
            return fn.return_type if fn else "unknown"
        if isinstance(node, IndexNode):
            base = self._infer(node.array)
            return base.rstrip("*") if base.endswith("*") else "int"
        if isinstance(node, PostfixOpNode):
            return self._infer(node.operand)
        return "unknown"

    # ── Pass 1 ─────────────────────────────────────────────────

    def _prescan(self, program: ProgramNode) -> None:
        """Register every top-level function signature."""
        for decl in program.declarations:
            if isinstance(decl, FuncDeclNode):
                params = [
                    ParamInfo(p.name, _type_str(p.type)) for p in decl.params
                ]
                self.symbol_table.declare_function(
                    decl.name,
                    _type_str(decl.return_type),
                    params,
                    decl.line,
                    0,
                )

    # ── Pass 2 — top-level visitors ────────────────────────────

    def visit_ProgramNode(self, n: ProgramNode) -> None:
        self._prescan(n)
        self.symbol_table.enter_scope()   # global scope
        for decl in n.declarations:
            decl.accept(self)
        self.symbol_table.exit_scope()

    def visit_FuncDeclNode(self, n: FuncDeclNode) -> None:
        prev = self._current_func
        self._current_func = self.symbol_table.lookup_function(n.name)

        self.symbol_table.enter_scope()   # parameter scope
        for p in n.params:
            if p.name:
                self.symbol_table.declare_variable(
                    p.name, _type_str(p.type), p.line, 0
                )
        # Body is a BlockNode → it opens its own nested scope
        n.body.accept(self)
        self.symbol_table.exit_scope()

        self._current_func = prev

    def visit_ParamNode(self, n: ParamNode) -> None:
        pass  # Handled in visit_FuncDeclNode

    # ── Block & statement visitors ─────────────────────────────

    def visit_BlockNode(self, n: BlockNode) -> None:
        self.symbol_table.enter_scope()
        for stmt in n.stmts:
            stmt.accept(self)
        self.symbol_table.exit_scope()

    def visit_VarDeclNode(self, n: VarDeclNode) -> None:
        ts = _type_str(n.type)
        for decl in n.declarators:
            # Visit initializer BEFORE declaring so "int x = x + 1;"
            # correctly flags x as undeclared.
            if decl.init is not None:
                decl.init.accept(self)
                init_type = self._infer(decl.init)
                self._check_assignment(ts, init_type, decl.line)

            existing = self.symbol_table.declare_variable(
                decl.name, ts, decl.line, 0
            )
            if existing is not None:
                self._err(
                    SemanticErrorKind.MULTIPLE_DECLARATION,
                    f"'{decl.name}' already declared in this scope at line {existing.line}",
                    decl.line,
                )

    def visit_VarDeclarator(self, n: VarDeclarator) -> None:
        pass  # Handled in visit_VarDeclNode

    def visit_IfNode(self, n: IfNode) -> None:
        n.condition.accept(self)
        n.then_branch.accept(self)
        if n.else_branch:
            n.else_branch.accept(self)

    def visit_WhileNode(self, n: WhileNode) -> None:
        n.condition.accept(self)
        n.body.accept(self)

    def visit_ForNode(self, n: ForNode) -> None:
        # The for-init declaration lives in this scope; the body opens its own.
        self.symbol_table.enter_scope()
        if n.init:      n.init.accept(self)
        if n.condition: n.condition.accept(self)
        if n.update:    n.update.accept(self)
        n.body.accept(self)
        self.symbol_table.exit_scope()

    def visit_ReturnNode(self, n: ReturnNode) -> None:
        if n.value:
            n.value.accept(self)
            if self._current_func:
                rt = self._infer(n.value)
                self._check_assignment(
                    self._current_func.return_type, rt, n.line,
                    context=f"return value of '{self._current_func.name}'",
                )

    def visit_JumpNode(self, n: JumpNode) -> None:
        pass  # break/continue — no semantic check

    def visit_ExprStmtNode(self, n: ExprStmtNode) -> None:
        n.expr.accept(self)

    # ── Expression visitors ────────────────────────────────────

    def visit_AssignNode(self, n: AssignNode) -> None:
        n.target.accept(self)
        n.value.accept(self)
        self._check_assignment(self._infer(n.target), self._infer(n.value), n.line)

    def visit_BinaryOpNode(self, n: BinaryOpNode) -> None:
        n.left.accept(self)
        n.right.accept(self)

        # Divide-by-zero
        if (
            n.op in ("/", "%")
            and isinstance(n.right, IntLiteralNode)
            and n.right.value == 0
        ):
            self._err(
                SemanticErrorKind.DIVIDE_BY_ZERO,
                f"division by zero in '{n.op}' expression",
                n.line,
            )

        # String operand on arithmetic
        if n.op in ("+", "-", "*", "/", "%"):
            lt = self._infer(n.left)
            rt = self._infer(n.right)
            if lt == "char*" and rt == "char*":
                self._err(
                    SemanticErrorKind.TYPE_MISMATCH,
                    f"invalid operands to '{n.op}': both operands are strings",
                    n.line, warning=True,
                )
            elif (lt == "char*" or rt == "char*") and n.op != "+":
                self._err(
                    SemanticErrorKind.TYPE_MISMATCH,
                    f"invalid operand to '{n.op}': string operand not allowed",
                    n.line, warning=True,
                )

    def visit_UnaryOpNode(self, n: UnaryOpNode) -> None:
        n.operand.accept(self)

    def visit_TernaryNode(self, n: TernaryNode) -> None:
        n.condition.accept(self)
        n.then_expr.accept(self)
        n.else_expr.accept(self)

    def visit_CallNode(self, n: CallNode) -> None:
        # Visit arguments first so errors inside them surface.
        for arg in n.args:
            arg.accept(self)

        fn = self.symbol_table.lookup_function(n.callee)
        if fn is None:
            if n.callee not in STDLIB_BUILTINS:
                self._err(
                    SemanticErrorKind.UNDECLARED_FUNCTION,
                    f"function '{n.callee}' is not declared",
                    n.line,
                )
            return

        # Argument count
        expected, got = len(fn.params), len(n.args)
        if expected != got:
            self._err(
                SemanticErrorKind.ARGUMENT_MISMATCH,
                f"'{n.callee}' expects {expected} argument"
                f"{'s' if expected != 1 else ''}, got {got}",
                n.line,
            )
            return

        # Per-argument type check
        for i, (param, arg_node) in enumerate(zip(fn.params, n.args)):
            arg_type = self._infer(arg_node)
            if not compatible(param.type_str, arg_type):
                self._err(
                    SemanticErrorKind.TYPE_MISMATCH,
                    (
                        f"argument {i + 1} of '{n.callee}': "
                        f"expected '{param.type_str}', got '{arg_type}'"
                    ),
                    n.line, warning=True,
                )

    def visit_IndexNode(self, n: IndexNode) -> None:
        n.array.accept(self)
        n.index.accept(self)

    def visit_PostfixOpNode(self, n: PostfixOpNode) -> None:
        n.operand.accept(self)

    def visit_IdentifierNode(self, n: IdentifierNode) -> None:
        if self.symbol_table.lookup_variable(n.name) is not None:
            return
        if self.symbol_table.lookup_function(n.name) is not None:
            return  # Allow naked function names (e.g. function pointers)
        self._err(
            SemanticErrorKind.UNDECLARED_VARIABLE,
            f"undeclared variable '{n.name}'",
            n.line,
        )

    # Literal leaf nodes — nothing to check
    def visit_IntLiteralNode(self,    n: IntLiteralNode)    -> None: pass
    def visit_FloatLiteralNode(self,  n: FloatLiteralNode)  -> None: pass
    def visit_StringLiteralNode(self, n: StringLiteralNode) -> None: pass
    def visit_CharLiteralNode(self,   n: CharLiteralNode)   -> None: pass
    def visit_TypeNode(self,          n: TypeNode)          -> None: pass

    def generic_visit(self, node: ASTNode) -> None:
        # Silently ignore unknown node types (e.g. _Hole from error recovery).
        pass

    # ── Type-compatibility helper ──────────────────────────────

    def _check_assignment(
        self,
        target_type: str,
        value_type:  str,
        line:        int,
        context:     str = "assignment",
    ) -> None:
        if "unknown" in (target_type, value_type) or compatible(target_type, value_type):
            return

        if is_integral(target_type) and is_float(value_type):
            self._err(
                SemanticErrorKind.TYPE_MISMATCH,
                f"{context}: assigning '{value_type}' to '{target_type}' — possible data loss",
                line, warning=True,
            )
        else:
            self._err(
                SemanticErrorKind.TYPE_MISMATCH,
                f"{context}: incompatible types '{value_type}' and '{target_type}'",
                line, warning=True,
            )


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def analyze_ast(ast: ProgramNode) -> tuple[list[SemanticError], SymbolTable]:
    """Run semantic analysis on an already-parsed AST."""
    analyzer = SemanticAnalyzer()
    analyzer.visit_ProgramNode(ast)
    return (
        sorted(analyzer.errors, key=lambda e: (e.line, e.column)),
        analyzer.symbol_table,
    )


def analyze_string(source: str) -> tuple[list[SemanticError], SymbolTable]:
    """Lex → parse → semantic-analyze a C source string."""
    try:
        ast = _parse_string(source)
        return analyze_ast(ast)
    except Exception:
        return [], SymbolTable()


def analyze_file(filename: str) -> tuple[list[SemanticError], SymbolTable]:
    """Lex → parse → semantic-analyze a C source file."""
    try:
        ast = _parse_file(filename)
        return analyze_ast(ast)
    except Exception:
        return [], SymbolTable()


# ─────────────────────────────────────────────────────────────
# Pretty reporter
# ─────────────────────────────────────────────────────────────

_KIND_COLOR: dict[SemanticErrorKind, str] = {
    SemanticErrorKind.UNDECLARED_VARIABLE:  "\033[31m",
    SemanticErrorKind.DIVIDE_BY_ZERO:       "\033[35m",
    SemanticErrorKind.ARGUMENT_MISMATCH:    "\033[33m",
    SemanticErrorKind.MULTIPLE_DECLARATION: "\033[36m",
    SemanticErrorKind.UNDECLARED_FUNCTION:  "\033[31m",
    SemanticErrorKind.TYPE_MISMATCH:        "\033[34m",
}
_RESET, _BOLD, _GREEN, _YELLOW = "\033[0m", "\033[1m", "\033[32m", "\033[33m"


def print_report(
    errors: list[SemanticError],
    source: Optional[str] = None,
    *,
    color: bool = True,
) -> None:
    """Pretty-print a list of semantic diagnostics."""
    if not errors:
        msg = (
            f"{_BOLD}{_GREEN}✓ No semantic errors.{_RESET}"
            if color else "No semantic errors."
        )
        print(msg)
        return

    src_lines = source.splitlines() if source else []

    for e in sorted(errors, key=lambda x: (x.line, x.column)):
        c = _KIND_COLOR.get(e.kind, "") if color else ""
        r = _RESET if color else ""
        b = _BOLD  if color else ""

        sev   = (f"{_YELLOW}WARNING{r}" if color else "WARNING") if e.is_warning else "ERROR"
        label = _KIND_LABEL[e.kind].upper()
        print(f"{b}{c}[{label}]{r} {sev}  line {e.line}, col {e.column}")
        print(f"  {e.message}")

        if src_lines and 1 <= e.line <= len(src_lines):
            print(f"  | {src_lines[e.line - 1]}")
            if e.column > 0:
                print(f"  | {' ' * (e.column - 1)}{c}^{r}")
        print()

    real     = sum(1 for e in errors if not e.is_warning)
    warnings = sum(1 for e in errors if e.is_warning)
    print(
        f"{_BOLD}{real} error(s), {warnings} warning(s)"
        f"{_RESET if color else ''}"
    )


# ─────────────────────────────────────────────────────────────
# CLI entry-point (for `python -m src.semantic <file>`)
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    src = open(sys.argv[1]).read() if len(sys.argv) > 1 else ""
    errs, table = analyze_string(src)
    table.print_table()
    print("\n── SEMANTIC DIAGNOSTICS ─────────────────────────────")
    print_report(errs, src)
