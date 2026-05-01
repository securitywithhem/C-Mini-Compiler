"""
Phase 3 — Multi-error syntax validator built on top of Phase 1 + Phase 2.

Four categories of error, each detected by a dedicated pass:

  UNMATCHED_BRACE    pre-parse token scan   (brace / bracket / paren balance)
  MISSING_SEMICOLON  recovering parser       (expect ';' failed → record + continue)
  INVALID_ASSIGN     recovering parser       (non-lvalue on left of '=')
  UNEXPECTED_TOKEN   recovering parser       (generic mismatch)
  MISSING_RETURN     post-parse AST visitor  (non-void function with no guaranteed return)

Public API
----------
  validate_file(filename)   → list[Diagnostic]
  validate_string(source)   → list[Diagnostic]
  validate_tokens(tokens)   → list[Diagnostic]
  print_report(diagnostics, source)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from .lexer import Token, TokenType, tokenize_file, tokenize_string
from .parser import (
    ASTNode, AssignNode, BinaryOpNode, BlockNode, CallNode,
    FloatLiteralNode, ForNode, FuncDeclNode, IdentifierNode, IfNode,
    IndexNode, IntLiteralNode, JumpNode, PostfixOpNode, ProgramNode,
    ReturnNode, StringLiteralNode, TernaryNode, UnaryOpNode,
    VarDeclarator, VarDeclNode, WhileNode, ExprStmtNode,
    Parser, Visitor,
    SyntaxError as CSyntaxError,
    _TYPE_KEYWORDS, _ASSIGN_OPS,
)


# ─────────────────────────────────────────────────────────────
# Diagnostic model
# ─────────────────────────────────────────────────────────────

class ErrorKind(Enum):
    MISSING_SEMICOLON = auto()
    UNMATCHED_BRACE   = auto()
    INVALID_ASSIGN    = auto()
    MISSING_RETURN    = auto()
    UNEXPECTED_TOKEN  = auto()


_KIND_LABEL = {
    ErrorKind.MISSING_SEMICOLON: "missing ';'",
    ErrorKind.UNMATCHED_BRACE:   "unmatched brace",
    ErrorKind.INVALID_ASSIGN:    "invalid assignment",
    ErrorKind.MISSING_RETURN:    "missing return",
    ErrorKind.UNEXPECTED_TOKEN:  "unexpected token",
}


@dataclass
class Diagnostic:
    kind:    ErrorKind
    message: str
    line:    int
    column:  int

    def __str__(self) -> str:
        label = _KIND_LABEL[self.kind]
        return f"[{label}]  line {self.line}, col {self.column}  — {self.message}"


# ─────────────────────────────────────────────────────────────
# Pass 1 — Pre-parse brace / bracket / paren balance
# ─────────────────────────────────────────────────────────────

_OPEN  = {"(": ")", "[": "]", "{": "}"}
_CLOSE = {v: k for k, v in _OPEN.items()}


def check_brace_balance(tokens: list[Token]) -> list[Diagnostic]:
    """
    Single-pass stack scan: every opener is pushed, every closer either
    matches the top or is reported.  Unclosed openers are reported at EOF.
    """
    diagnostics: list[Diagnostic] = []
    stack: list[Token] = []   # tokens of unmatched openers

    for tok in tokens:
        if tok.type is not TokenType.SEPARATOR:
            continue

        if tok.value in _OPEN:
            stack.append(tok)

        elif tok.value in _CLOSE:
            expected_open = _CLOSE[tok.value]
            if not stack:
                diagnostics.append(Diagnostic(
                    ErrorKind.UNMATCHED_BRACE,
                    f"unexpected '{tok.value}' — no matching '{expected_open}'",
                    tok.line, tok.column,
                ))
            elif stack[-1].value != expected_open:
                opener = stack[-1]
                diagnostics.append(Diagnostic(
                    ErrorKind.UNMATCHED_BRACE,
                    f"'{tok.value}' closes '{opener.value}' opened at "
                    f"line {opener.line}, col {opener.column}",
                    tok.line, tok.column,
                ))
                stack.pop()
            else:
                stack.pop()

    for opener in stack:
        closing = _OPEN[opener.value]
        diagnostics.append(Diagnostic(
            ErrorKind.UNMATCHED_BRACE,
            f"'{opener.value}' at line {opener.line}, col {opener.column} "
            f"was never closed with '{closing}'",
            opener.line, opener.column,
        ))

    return diagnostics


# ─────────────────────────────────────────────────────────────
# Pass 2 — Recovering parser
# ─────────────────────────────────────────────────────────────

# Sync points: after an error we skip forward until we can safely restart.
_STMT_STARTERS = _TYPE_KEYWORDS | {"if", "while", "for", "return"}
_SYNC_VALUES   = {";", "{", "}"}


class _Hole(ASTNode):
    """Sentinel inserted into the AST where a node failed to parse."""


class ValidatingParser(Parser):
    """
    Subclass of Parser that catches CSyntaxError per-statement,
    records a Diagnostic, synchronises the token stream, and continues
    so subsequent statements are still checked.
    """

    def __init__(self, tokens: list[Token]):
        super().__init__(tokens)
        self.diagnostics: list[Diagnostic] = []

    # ── Diagnostic helpers ─────────────────────────────────────

    def _add(self, kind: ErrorKind, message: str, tok: Optional[Token]):
        line = tok.line   if tok else 0
        col  = tok.column if tok else 0
        self.diagnostics.append(Diagnostic(kind, message, line, col))

    def _classify_and_add(self, exc: CSyntaxError):
        tok = exc.token
        msg = exc.args[0]

        if "expected ';'" in msg:
            kind = ErrorKind.MISSING_SEMICOLON
        elif "unmatched" in msg.lower() or "expected '}'" in msg or "expected '{'" in msg:
            kind = ErrorKind.UNMATCHED_BRACE
        else:
            kind = ErrorKind.UNEXPECTED_TOKEN

        self._add(kind, msg, tok)

    # ── Panic-mode synchronisation ─────────────────────────────

    def _synchronize(self):
        """Skip tokens until a likely statement boundary."""
        while not self._s.is_at_end():
            tok = self._s.peek()
            # consume the ';' so the next statement starts cleanly
            if tok.value == ";":
                self._s.advance()
                return
            # stop before these — let the caller decide
            if tok.value in ("{", "}"):
                return
            if tok.type is TokenType.KEYWORD and tok.value in _STMT_STARTERS:
                return
            self._s.advance()

    # ── Override: top-level (per-declaration recovery) ─────────

    def parse(self) -> ProgramNode:
        decls: list[ASTNode] = []
        while not self._s.is_at_end():
            try:
                decls.append(self._top_decl())
            except CSyntaxError as exc:
                self._classify_and_add(exc)
                self._synchronize()
        node = ProgramNode(decls)
        node.line = 1
        return node

    # ── Override: block (per-statement recovery) ───────────────

    def _block(self) -> BlockNode:
        line = self._s.peek().line if self._s.peek() else 0

        # Missing opening brace
        if not self._s.check_value("{"):
            tok = self._s.peek()
            self._add(
                ErrorKind.UNMATCHED_BRACE,
                f"expected '{{', got {repr(tok.value) if tok else 'EOF'}",
                tok,
            )
            # Treat the next statement as a single-statement body
            node = BlockNode([])
            node.line = line
            return node

        self._s.advance()  # consume '{'
        stmts: list[ASTNode] = []

        while not self._s.check_value("}") and not self._s.is_at_end():
            try:
                s = self._stmt()
                if s is not None:
                    stmts.append(s)
            except CSyntaxError as exc:
                self._classify_and_add(exc)
                self._synchronize()

        # Missing closing brace
        if self._s.is_at_end():
            self._add(
                ErrorKind.UNMATCHED_BRACE,
                "reached end of file without closing '}'",
                None,
            )
        else:
            self._s.advance()  # consume '}'

        node = BlockNode(stmts)
        node.line = line
        return node

    # ── Override: expression statement (lvalue + semicolon) ────

    def _expr_stmt(self):
        line = self._s.peek().line if self._s.peek() else 0

        try:
            expr = self._expr()
        except CSyntaxError as exc:
            self._classify_and_add(exc)
            self._synchronize()
            hole = _Hole()
            hole.line = line
            node = ExprStmtNode(hole)
            node.line = line
            return node

        # After a successful expression parse, if an assign op is still sitting
        # in the stream the assignment() rule didn't consume it — meaning the
        # left-hand side is not a valid lvalue (e.g. a literal or a call result).
        if self._s.check_value(*_ASSIGN_OPS):
            op_tok = self._s.peek()
            self._add(
                ErrorKind.INVALID_ASSIGN,
                f"left-hand side of '{op_tok.value}' is not a valid lvalue "
                f"(got {type(expr).__name__})",
                op_tok,
            )
            self._s.advance()  # consume the bad op
            try:
                self._expr()   # consume rhs so we reach ';'
            except CSyntaxError:
                pass

        # Semicolon with a descriptive message
        if not self._s.check_value(";"):
            tok = self._s.peek()
            ctx = _expr_context(expr)
            self._add(
                ErrorKind.MISSING_SEMICOLON,
                f"missing ';' after {ctx} "
                f"(got {repr(tok.value) if tok else 'EOF'})",
                tok,
            )
        else:
            self._s.advance()

        node = ExprStmtNode(expr)
        node.line = line
        return node

    # ── Override: var decl (semicolon detection) ───────────────

    def _var_decl_rest(self, typ, first_name, name_tok, top_level=False):
        try:
            return super()._var_decl_rest(typ, first_name, name_tok, top_level)
        except CSyntaxError as exc:
            tok = exc.token
            if tok and "expected ';'" in exc.args[0]:
                self._add(
                    ErrorKind.MISSING_SEMICOLON,
                    f"missing ';' after declaration of '{first_name}'",
                    tok,
                )
                # pretend semicolon was consumed; stream is already past the bad token
            else:
                self._classify_and_add(exc)
            # build a minimal VarDeclNode so the rest of the tree is intact
            decl = VarDeclarator(first_name, None)
            decl.line = name_tok.line
            node = VarDeclNode(typ, [decl])
            node.line = name_tok.line
            return node

    # ── Override: return statement (semicolon detection) ────────

    def _return_stmt(self):
        line = self._s.peek().line
        self._s.expect_value("return")
        value = None
        if not self._s.check_value(";"):
            try:
                value = self._expr()
            except CSyntaxError as exc:
                self._classify_and_add(exc)
                self._synchronize()

        if not self._s.check_value(";"):
            tok = self._s.peek()
            self._add(
                ErrorKind.MISSING_SEMICOLON,
                f"missing ';' after return statement "
                f"(got {repr(tok.value) if tok else 'EOF'})",
                tok,
            )
        else:
            self._s.advance()

        node = ReturnNode(value)
        node.line = line
        return node


def _lvalue_str(node: ASTNode) -> str:
    if isinstance(node, IdentifierNode):
        return f"'{node.name}'"
    if isinstance(node, IndexNode):
        return f"'{_lvalue_str(node.array)}[...]'"
    if isinstance(node, UnaryOpNode):
        return f"'{node.op}{_lvalue_str(node.operand)}'"
    return "expression"


def _expr_context(expr: ASTNode) -> str:
    """Human-readable label for an expression node (used in error messages)."""
    if isinstance(expr, IdentifierNode):
        return f"identifier '{expr.name}'"
    if isinstance(expr, CallNode):
        return f"call to '{expr.callee}()'"
    if isinstance(expr, AssignNode):
        return f"assignment to {_lvalue_str(expr.target)}"
    if isinstance(expr, BinaryOpNode):
        return f"'{expr.op}' expression"
    if isinstance(expr, UnaryOpNode):
        return f"unary '{expr.op}' expression"
    if isinstance(expr, IntLiteralNode):
        return "integer literal"
    if isinstance(expr, FloatLiteralNode):
        return "float literal"
    if isinstance(expr, StringLiteralNode):
        return "string literal"
    return "expression"


# ─────────────────────────────────────────────────────────────
# Pass 3 — Post-parse semantic checks
# ─────────────────────────────────────────────────────────────

def _guaranteed_return(stmt: ASTNode) -> bool:
    """
    Conservative check: does `stmt` definitely reach a return on every path?
    Used to detect missing-return situations in non-void functions.
    """
    if isinstance(stmt, ReturnNode):
        return True
    if isinstance(stmt, BlockNode):
        return any(_guaranteed_return(s) for s in stmt.stmts) and \
               _guaranteed_return(stmt.stmts[-1]) if stmt.stmts else False
    if isinstance(stmt, IfNode):
        return (stmt.else_branch is not None
                and _guaranteed_return(stmt.then_branch)
                and _guaranteed_return(stmt.else_branch))
    if isinstance(stmt, (WhileNode, ForNode)):
        # We can't prove termination, so conservatively False
        return False
    return False


def _collect_returns(node: ASTNode, out: list[ReturnNode]):
    """Recursively collect all ReturnNode instances under `node`."""
    if isinstance(node, ReturnNode):
        out.append(node)
        return
    for attr in vars(node).values():
        if isinstance(attr, ASTNode):
            _collect_returns(attr, out)
        elif isinstance(attr, list):
            for item in attr:
                if isinstance(item, ASTNode):
                    _collect_returns(item, out)


class SemanticChecker(Visitor):
    """
    AST visitor that checks:
      1. Non-void functions guarantee a return statement.
      2. Assignment targets are valid lvalues (second layer after parser check).
    """

    def __init__(self):
        self.diagnostics: list[Diagnostic] = []
        self._current_func: Optional[FuncDeclNode] = None

    def _add(self, kind: ErrorKind, message: str, line: int, col: int = 0):
        self.diagnostics.append(Diagnostic(kind, message, line, col))

    # ── Visitor methods ────────────────────────────────────────

    def visit_ProgramNode(self, n: ProgramNode):
        for decl in n.declarations:
            decl.accept(self)

    def visit_FuncDeclNode(self, n: FuncDeclNode):
        prev = self._current_func
        self._current_func = n
        n.body.accept(self)
        self._current_func = prev

        # Missing-return check — skip void functions
        if n.return_type.base == "void":
            return

        returns: list[ReturnNode] = []
        _collect_returns(n.body, returns)

        if not returns:
            self._add(
                ErrorKind.MISSING_RETURN,
                f"function '{n.name}' has return type '{n.return_type.base}' "
                f"but contains no return statement",
                n.line,
            )
        elif not _guaranteed_return(n.body):
            self._add(
                ErrorKind.MISSING_RETURN,
                f"function '{n.name}' may not return on all paths "
                f"(return type '{n.return_type.base}')",
                n.line,
            )

    def visit_VarDeclNode(self, n: VarDeclNode):
        for d in n.declarators:
            if d.init is not None:
                d.init.accept(self)

    def visit_BlockNode(self, n: BlockNode):
        for s in n.stmts:
            s.accept(self)

    def visit_IfNode(self, n: IfNode):
        n.condition.accept(self)
        n.then_branch.accept(self)
        if n.else_branch:
            n.else_branch.accept(self)

    def visit_WhileNode(self, n: WhileNode):
        n.condition.accept(self)
        n.body.accept(self)

    def visit_ForNode(self, n: ForNode):
        if n.init:      n.init.accept(self)
        if n.condition: n.condition.accept(self)
        if n.update:    n.update.accept(self)
        n.body.accept(self)

    def visit_ReturnNode(self, n: ReturnNode):
        if n.value:
            n.value.accept(self)

    def visit_ExprStmtNode(self, n: ExprStmtNode):
        n.expr.accept(self)

    def visit_AssignNode(self, n: AssignNode):
        # target is now an ASTNode (IdentifierNode / IndexNode / UnaryOpNode)
        n.target.accept(self)
        n.value.accept(self)

    def visit_BinaryOpNode(self, n: BinaryOpNode):
        n.left.accept(self)
        n.right.accept(self)

    def visit_UnaryOpNode(self, n: UnaryOpNode):
        n.operand.accept(self)

    def visit_TernaryNode(self, n: TernaryNode):
        n.condition.accept(self)
        n.then_expr.accept(self)
        n.else_expr.accept(self)

    def visit_CallNode(self, n: CallNode):
        for a in n.args:
            a.accept(self)

    def visit_IndexNode(self, n: IndexNode):
        n.array.accept(self)
        n.index.accept(self)

    def visit_PostfixOpNode(self, n: PostfixOpNode):
        n.operand.accept(self)

    def visit_JumpNode(self, n: JumpNode): pass   # continue / break — no checks needed

    # Leaves — nothing to recurse into
    def visit_IdentifierNode(self, n):   pass
    def visit_IntLiteralNode(self, n):   pass
    def visit_FloatLiteralNode(self, n): pass
    def visit_StringLiteralNode(self, n): pass
    def visit_CharLiteralNode(self, n):  pass
    def visit_TypeNode(self, n):         pass
    def visit_VarDeclarator(self, n):    pass
    def visit__Hole(self, n):            pass  # error-recovery placeholder


# ─────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────

def validate_tokens(tokens: list[Token]) -> list[Diagnostic]:
    """Run all three passes and return every diagnostic, sorted by line."""
    # Pass 1 — brace balance (token scan, no AST needed)
    diags = check_brace_balance(tokens)

    # Pass 2 — recovering parse (structural checks + semicolons + lvalues)
    vp = ValidatingParser(tokens)
    ast = vp.parse()
    diags.extend(vp.diagnostics)

    # Pass 3 — semantic checks (missing return, …)
    sc = SemanticChecker()
    sc.visit_ProgramNode(ast)
    diags.extend(sc.diagnostics)

    return sorted(diags, key=lambda d: (d.line, d.column))


def validate_string(source: str) -> list[Diagnostic]:
    return validate_tokens(tokenize_string(source))


def validate_file(filename: str) -> list[Diagnostic]:
    return validate_tokens(tokenize_file(filename))


# ─────────────────────────────────────────────────────────────
# Pretty reporter
# ─────────────────────────────────────────────────────────────

_KIND_COLOR = {
    ErrorKind.MISSING_SEMICOLON: "\033[33m",  # yellow
    ErrorKind.UNMATCHED_BRACE:   "\033[31m",  # red
    ErrorKind.INVALID_ASSIGN:    "\033[35m",  # magenta
    ErrorKind.MISSING_RETURN:    "\033[36m",  # cyan
    ErrorKind.UNEXPECTED_TOKEN:  "\033[31m",  # red
}
_RESET = "\033[0m"
_BOLD  = "\033[1m"


def print_report(
    diagnostics: list[Diagnostic],
    source: Optional[str] = None,
    *,
    color: bool = True,
):
    if not diagnostics:
        ok = f"{_BOLD}\033[32m✓ No errors found.{_RESET}" if color else "No errors found."
        print(ok)
        return

    lines = source.splitlines() if source else []

    for d in diagnostics:
        c = _KIND_COLOR.get(d.kind, "") if color else ""
        r = _RESET if color else ""
        b = _BOLD  if color else ""
        label = _KIND_LABEL[d.kind].upper()
        print(f"{b}{c}[{label}]{r}  line {d.line}, col {d.column}")
        print(f"  {d.message}")

        # Print the source line with a caret
        if lines and 1 <= d.line <= len(lines):
            src_line = lines[d.line - 1]
            print(f"  | {src_line}")
            if d.column > 0:
                print(f"  | {' ' * (d.column - 1)}{c}^{r}")
        print()

    total = len(diagnostics)
    by_kind: dict[ErrorKind, int] = {}
    for d in diagnostics:
        by_kind[d.kind] = by_kind.get(d.kind, 0) + 1

    summary_parts = [f"{v} {_KIND_LABEL[k]}" for k, v in by_kind.items()]
    print(f"{_BOLD}{total} error(s): {', '.join(summary_parts)}{_RESET if color else ''}")


# ─────────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        src_text = open(sys.argv[1]).read()
        diags = validate_file(sys.argv[1])
    else:
        # Demonstration source — deliberately contains every error type
        src_text = r"""
#include <stdio.h>

/* 1. missing semicolon after variable declaration */
int globalVar = 10

/* 2. unmatched brace — extra '}' */
}

/* 3. valid function — should produce no errors */
int add(int a, int b) {
    return a + b;
}

/* 4. missing return — non-void function with no return */
int noReturn(int x) {
    int y = x + 1;
}

/* 5. missing return on some paths */
int partialReturn(int x) {
    if (x > 0) {
        return x;
    }
}

/* 6. missing semicolon after return */
int missingSemiReturn(int x) {
    return x + 1
}

/* 7. invalid assignment target (non-lvalue) */
void badAssign() {
    int a = 5;
    int b = 3;
    a + b = 10;
}

/* 8. missing semicolon in expression statement */
void missingExprSemi() {
    int x = 5;
    x = x + 1
    printf("%d\n", x);
}

int main() {
    printf("hello\n");
    return 0;
}
"""
        diags = validate_string(src_text)

    print_report(diags, src_text)
