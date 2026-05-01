"""
Unit tests for the parser (Phase 2).

Verifies that the recursive-descent parser produces the correct AST
shape for every grammar construct it supports.
"""

from __future__ import annotations

import sys

from src.parser import (
    AssignNode,
    BinaryOpNode,
    BlockNode,
    CallNode,
    CharLiteralNode,
    ExprStmtNode,
    FloatLiteralNode,
    ForNode,
    FuncDeclNode,
    IdentifierNode,
    IfNode,
    IntLiteralNode,
    ParamNode,
    ProgramNode,
    ReturnNode,
    StringLiteralNode,
    UnaryOpNode,
    VarDeclNode,
    WhileNode,
    parse_string,
    SyntaxError as PSyntaxError,
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


def _parse(src: str) -> ProgramNode:
    return parse_string(src)


# ═════════════════════════════════════════════════════════════
# 1. Empty program
# ═════════════════════════════════════════════════════════════
print("\n── 1. EMPTY PROGRAM ────────────────────────────────────")

ast = _parse("")
_check("empty source → ProgramNode with no declarations",
       isinstance(ast, ProgramNode) and ast.declarations == [])

# ═════════════════════════════════════════════════════════════
# 2. Function declarations
# ═════════════════════════════════════════════════════════════
print("\n── 2. FUNCTION DECLARATIONS ────────────────────────────")

ast = _parse("int main() { return 0; }")
_check("one top-level declaration", len(ast.declarations) == 1)
fn = ast.declarations[0]
_check("decl is FuncDeclNode", isinstance(fn, FuncDeclNode))
_check("function name is 'main'", fn.name == "main")
_check("return type is 'int'", fn.return_type.base == "int")
_check("no parameters", fn.params == [])
_check("body is BlockNode", isinstance(fn.body, BlockNode))

ast = _parse("int add(int a, int b) { return a + b; }")
fn = ast.declarations[0]
_check("two parameters", len(fn.params) == 2)
_check(
    "parameter names a, b",
    [p.name for p in fn.params] == ["a", "b"],
)
_check(
    "parameter types int, int",
    all(isinstance(p, ParamNode) and p.type.base == "int" for p in fn.params),
)

# ═════════════════════════════════════════════════════════════
# 3. Variable declarations
# ═════════════════════════════════════════════════════════════
print("\n── 3. VARIABLE DECLARATIONS ────────────────────────────")

ast = _parse("int main() { int x = 5; int y; return 0; }")
body_stmts = ast.declarations[0].body.stmts
_check("first stmt is VarDeclNode", isinstance(body_stmts[0], VarDeclNode))
_check("x declarator has init", body_stmts[0].declarators[0].init is not None)
_check(
    "init is IntLiteralNode(5)",
    isinstance(body_stmts[0].declarators[0].init, IntLiteralNode)
    and body_stmts[0].declarators[0].init.value == 5,
)
_check("second stmt has no init", body_stmts[1].declarators[0].init is None)

ast = _parse("int main() { int x = 1, y = 2, z; return 0; }")
decl = ast.declarations[0].body.stmts[0]
_check("multi-declarator → 3 declarators", len(decl.declarators) == 3)

# ═════════════════════════════════════════════════════════════
# 4. Expressions: precedence
# ═════════════════════════════════════════════════════════════
print("\n── 4. OPERATOR PRECEDENCE ──────────────────────────────")

ast = _parse("int main() { int x = 2 + 3 * 4; return 0; }")
init = ast.declarations[0].body.stmts[0].declarators[0].init
# Should parse as: 2 + (3 * 4)
_check("top is '+'", isinstance(init, BinaryOpNode) and init.op == "+")
_check("left is IntLiteral(2)", isinstance(init.left, IntLiteralNode) and init.left.value == 2)
_check(
    "right is BinaryOpNode '*'",
    isinstance(init.right, BinaryOpNode) and init.right.op == "*",
)

ast = _parse("int main() { int x = (2 + 3) * 4; return 0; }")
init = ast.declarations[0].body.stmts[0].declarators[0].init
_check("with parens: top is '*'", isinstance(init, BinaryOpNode) and init.op == "*")
_check(
    "left is BinaryOpNode '+'",
    isinstance(init.left, BinaryOpNode) and init.left.op == "+",
)

# ═════════════════════════════════════════════════════════════
# 5. Assignments
# ═════════════════════════════════════════════════════════════
print("\n── 5. ASSIGNMENTS ──────────────────────────────────────")

ast = _parse("int main() { int x; x = 10; return 0; }")
expr_stmt = ast.declarations[0].body.stmts[1]
_check("ExprStmtNode wraps the assignment", isinstance(expr_stmt, ExprStmtNode))
_check("inner is AssignNode", isinstance(expr_stmt.expr, AssignNode))
_check("operator is '='", expr_stmt.expr.op == "=")
_check("target is IdentifierNode", isinstance(expr_stmt.expr.target, IdentifierNode))

# ═════════════════════════════════════════════════════════════
# 6. Function calls
# ═════════════════════════════════════════════════════════════
print("\n── 6. FUNCTION CALLS ───────────────────────────────────")

ast = _parse("int main() { foo(1, 2, 3); return 0; }")
call = ast.declarations[0].body.stmts[0].expr
_check("expression is CallNode", isinstance(call, CallNode))
_check("callee is 'foo'", call.callee == "foo")
_check("3 arguments", len(call.args) == 3)
_check(
    "all arguments are IntLiteralNode",
    all(isinstance(a, IntLiteralNode) for a in call.args),
)

# ═════════════════════════════════════════════════════════════
# 7. Control flow
# ═════════════════════════════════════════════════════════════
print("\n── 7. CONTROL FLOW ─────────────────────────────────────")

ast = _parse("""
int main() {
    if (1) { return 1; } else { return 0; }
}
""")
ifn = ast.declarations[0].body.stmts[0]
_check("if-stmt is IfNode", isinstance(ifn, IfNode))
_check("else branch present", ifn.else_branch is not None)

ast = _parse("int main() { while (1) { return 0; } }")
_check(
    "while-stmt is WhileNode",
    isinstance(ast.declarations[0].body.stmts[0], WhileNode),
)

ast = _parse("int main() { for (int i = 0; i < 10; i++) { } return 0; }")
forn = ast.declarations[0].body.stmts[0]
_check("for-stmt is ForNode", isinstance(forn, ForNode))
_check("for has init, condition, update",
       forn.init is not None and forn.condition is not None and forn.update is not None)

# ═════════════════════════════════════════════════════════════
# 8. Literals
# ═════════════════════════════════════════════════════════════
print("\n── 8. LITERALS ─────────────────────────────────────────")

ast = _parse('int main() { int a = 42; float b = 3.14; char c = \'x\'; return 0; }')
stmts = ast.declarations[0].body.stmts
_check("int literal", isinstance(stmts[0].declarators[0].init, IntLiteralNode))
_check("float literal", isinstance(stmts[1].declarators[0].init, FloatLiteralNode))
_check("char literal", isinstance(stmts[2].declarators[0].init, CharLiteralNode))

ast = _parse('int main() { printf("hello"); return 0; }')
arg = ast.declarations[0].body.stmts[0].expr.args[0]
_check("string literal", isinstance(arg, StringLiteralNode))

# ═════════════════════════════════════════════════════════════
# 9. Unary operators
# ═════════════════════════════════════════════════════════════
print("\n── 9. UNARY OPERATORS ──────────────────────────────────")

ast = _parse("int main() { int x = -5; int y = !x; return 0; }")
init1 = ast.declarations[0].body.stmts[0].declarators[0].init
init2 = ast.declarations[0].body.stmts[1].declarators[0].init
_check("'-5' is UnaryOpNode '-'", isinstance(init1, UnaryOpNode) and init1.op == "-")
_check("'!x' is UnaryOpNode '!'", isinstance(init2, UnaryOpNode) and init2.op == "!")

# ═════════════════════════════════════════════════════════════
# 10. Multiple top-level declarations
# ═════════════════════════════════════════════════════════════
print("\n── 10. MULTIPLE TOP-LEVEL DECLS ───────────────────────")

ast = _parse("""
int globalVar = 5;
int helper(int x) { return x; }
int main() { return helper(globalVar); }
""")
_check("3 top-level declarations", len(ast.declarations) == 3)
_check("first is VarDeclNode (global)", isinstance(ast.declarations[0], VarDeclNode))
_check("second is FuncDeclNode (helper)", isinstance(ast.declarations[1], FuncDeclNode))
_check("third is FuncDeclNode (main)", isinstance(ast.declarations[2], FuncDeclNode))

# ═════════════════════════════════════════════════════════════
# 11. Syntax error raised on bad input
# ═════════════════════════════════════════════════════════════
print("\n── 11. SYNTAX ERRORS ──────────────────────────────────")

raised = False
try:
    _parse("int main( {}")   # Bad syntax: missing ')'
except PSyntaxError:
    raised = True
_check("malformed program raises SyntaxError", raised)

# ═════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════

total = _PASS + _FAIL
print(f"""
══════════════════════════════════════════════════════════
  Parser tests: {_PASS}/{total} passed   ({_FAIL} failed)
══════════════════════════════════════════════════════════
""")

sys.exit(0 if _FAIL == 0 else 1)
