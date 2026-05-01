"""
Phase 2 — Recursive-descent parser for a simplified C grammar.
Consumes Token objects produced by c_lexer.py (Phase 1).

Grammar (EBNF)
--------------
program        → top_decl*
top_decl       → func_decl | var_decl
func_decl      → type IDENTIFIER '(' param_list? ')' block
var_decl       → type init_declarator (',' init_declarator)* ';'
init_declarator→ IDENTIFIER ('=' expr)?
param_list     → param (',' param)*
param          → type IDENTIFIER?

block          → '{' stmt* '}'
stmt           → var_decl | if_stmt | while_stmt | for_stmt
               | return_stmt | block | expr_stmt

if_stmt        → 'if' '(' expr ')' stmt ('else' stmt)?
while_stmt     → 'while' '(' expr ')' stmt
for_stmt       → 'for' '(' for_init expr? ';' expr? ')' stmt
for_init       → var_decl | expr_stmt | ';'
return_stmt    → 'return' expr? ';'
expr_stmt      → expr ';'

expr           → assignment
assignment     → IDENTIFIER assign_op assignment | conditional
assign_op      → '=' | '+=' | '-=' | '*=' | '/=' | '%=' | '&=' | '|=' | '^='
conditional    → logical_or ('?' expr ':' conditional)?
logical_or     → logical_and ('||' logical_and)*
logical_and    → equality   ('&&' equality)*
equality       → relational (('==' | '!=') relational)*
relational     → additive   (('<' | '>' | '<=' | '>=') additive)*
additive       → multiplicative (('+' | '-') multiplicative)*
multiplicative → unary (('*' | '/' | '%') unary)*
unary          → ('+' | '-' | '!' | '~' | '&') unary | postfix
postfix        → primary postfix_op*
postfix_op     → '++' | '--' | '[' expr ']' | '(' arg_list? ')'
primary        → INTEGER | FLOAT | STRING | CHAR | IDENTIFIER | '(' expr ')'
arg_list       → expr (',' expr)*
type           → type_kw+ '*'*
type_kw        → 'int' | 'float' | 'double' | 'char' | 'void'
               | 'long' | 'short' | 'unsigned' | 'signed'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .lexer import Token, TokenType, tokenize_file, tokenize_string


# ─────────────────────────────────────────────────────────────
# AST nodes
# ─────────────────────────────────────────────────────────────

@dataclass
class ASTNode:
    line: int = field(default=0, init=False, repr=False)

    def accept(self, visitor: "Visitor"):
        method = f"visit_{type(self).__name__}"
        return getattr(visitor, method, visitor.generic_visit)(self)


# ── Types ──────────────────────────────────────────────────────

@dataclass
class TypeNode(ASTNode):
    """e.g.  int, unsigned long, char *"""
    base: str        # canonical base string, e.g. "unsigned long"
    pointer_depth: int = 0

    def __str__(self):
        return self.base + " " + "*" * self.pointer_depth


# ── Declarations ───────────────────────────────────────────────

@dataclass
class VarDeclarator(ASTNode):
    name: str
    init: Optional[ASTNode] = None


@dataclass
class VarDeclNode(ASTNode):
    type: TypeNode
    declarators: list[VarDeclarator]


@dataclass
class ParamNode(ASTNode):
    type: TypeNode
    name: Optional[str]


@dataclass
class FuncDeclNode(ASTNode):
    return_type: TypeNode
    name: str
    params: list[ParamNode]
    body: "BlockNode"


@dataclass
class ProgramNode(ASTNode):
    declarations: list[ASTNode]


# ── Statements ─────────────────────────────────────────────────

@dataclass
class BlockNode(ASTNode):
    stmts: list[ASTNode]


@dataclass
class IfNode(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode]


@dataclass
class WhileNode(ASTNode):
    condition: ASTNode
    body: ASTNode


@dataclass
class ForNode(ASTNode):
    init: Optional[ASTNode]      # VarDeclNode | ExprStmtNode | None
    condition: Optional[ASTNode]
    update: Optional[ASTNode]
    body: ASTNode


@dataclass
class ReturnNode(ASTNode):
    value: Optional[ASTNode]


@dataclass
class JumpNode(ASTNode):
    """continue or break statement."""
    keyword: str


@dataclass
class ExprStmtNode(ASTNode):
    expr: ASTNode


# ── Expressions ────────────────────────────────────────────────

@dataclass
class AssignNode(ASTNode):
    target: ASTNode   # IdentifierNode | IndexNode | UnaryOpNode(*)
    op: str
    value: ASTNode


@dataclass
class BinaryOpNode(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode


@dataclass
class UnaryOpNode(ASTNode):
    op: str
    operand: ASTNode


@dataclass
class TernaryNode(ASTNode):
    condition: ASTNode
    then_expr: ASTNode
    else_expr: ASTNode


@dataclass
class CallNode(ASTNode):
    callee: str
    args: list[ASTNode]


@dataclass
class IndexNode(ASTNode):
    array: ASTNode
    index: ASTNode


@dataclass
class PostfixOpNode(ASTNode):
    operand: ASTNode
    op: str   # '++' or '--'


@dataclass
class IdentifierNode(ASTNode):
    name: str


@dataclass
class IntLiteralNode(ASTNode):
    value: int


@dataclass
class FloatLiteralNode(ASTNode):
    value: float


@dataclass
class StringLiteralNode(ASTNode):
    value: str


@dataclass
class CharLiteralNode(ASTNode):
    value: str


# ─────────────────────────────────────────────────────────────
# Syntax error
# ─────────────────────────────────────────────────────────────

class SyntaxError(Exception):
    def __init__(self, message: str, token: Optional[Token] = None):
        loc = f" (line {token.line}, col {token.column})" if token else ""
        super().__init__(f"SyntaxError{loc}: {message}")
        self.token = token


# ─────────────────────────────────────────────────────────────
# Token stream
# ─────────────────────────────────────────────────────────────

_TYPE_KEYWORDS = frozenset({
    "int", "float", "double", "char", "void",
    "long", "short", "unsigned", "signed",
})

_ASSIGN_OPS = frozenset({
    "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
})


class TokenStream:
    """Thin wrapper around a flat token list with look-ahead and consume helpers."""

    def __init__(self, tokens: list[Token]):
        # Strip preprocessor directives — they're handled before parsing
        self._tokens = [t for t in tokens if t.type is not TokenType.PREPROCESSOR]
        self._pos = 0

    # ── Core primitives ────────────────────────────────────────

    def peek(self, offset: int = 0) -> Optional[Token]:
        idx = self._pos + offset
        return self._tokens[idx] if idx < len(self._tokens) else None

    def advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def is_at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    # ── Match helpers ──────────────────────────────────────────

    def check_type(self, *types: TokenType) -> bool:
        t = self.peek()
        return t is not None and t.type in types

    def check_value(self, *values: str) -> bool:
        t = self.peek()
        return t is not None and t.value in values

    def match_value(self, *values: str) -> Optional[Token]:
        if self.check_value(*values):
            return self.advance()
        return None

    def expect_value(self, value: str) -> Token:
        tok = self.peek()
        if tok is None or tok.value != value:
            got = repr(tok.value) if tok else "EOF"
            raise SyntaxError(f"expected '{value}', got {got}", tok)
        return self.advance()

    def expect_type(self, ttype: TokenType) -> Token:
        tok = self.peek()
        if tok is None or tok.type is not ttype:
            got = f"{tok.type.name} {tok.value!r}" if tok else "EOF"
            raise SyntaxError(f"expected {ttype.name}, got {got}", tok)
        return self.advance()


# ─────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────

class Parser:
    def __init__(self, tokens: list[Token]):
        self._s = TokenStream(tokens)

    # ── Entry point ────────────────────────────────────────────

    def parse(self) -> ProgramNode:
        decls: list[ASTNode] = []
        while not self._s.is_at_end():
            decls.append(self._top_decl())
        node = ProgramNode(decls)
        node.line = 1
        return node

    # ── Top-level declarations ─────────────────────────────────

    def _top_decl(self) -> ASTNode:
        typ = self._type()
        name_tok = self._s.expect_type(TokenType.IDENTIFIER)
        name = name_tok.value

        if self._s.check_value("("):
            return self._func_decl_rest(typ, name, name_tok.line)
        return self._var_decl_rest(typ, name, name_tok, top_level=True)

    def _func_decl_rest(self, ret_type: TypeNode, name: str, line: int) -> FuncDeclNode:
        self._s.expect_value("(")
        params = self._param_list()
        self._s.expect_value(")")
        body = self._block()
        node = FuncDeclNode(ret_type, name, params, body)
        node.line = line
        return node

    def _param_list(self) -> list[ParamNode]:
        params: list[ParamNode] = []
        if self._s.check_value(")"):
            return params
        if self._s.check_value("void") and self._s.peek(1) and self._s.peek(1).value == ")":
            self._s.advance()  # consume 'void'
            return params
        params.append(self._param())
        while self._s.match_value(","):
            if self._s.check_value("..."):
                self._s.advance()
                break
            params.append(self._param())
        return params

    def _param(self) -> ParamNode:
        line = self._s.peek().line if self._s.peek() else 0
        typ = self._type()
        name = None
        if self._s.check_type(TokenType.IDENTIFIER):
            name = self._s.advance().value
        # consume optional array brackets:  argv[]  or  argv[10]
        while self._s.check_value("["):
            self._s.advance()
            if not self._s.check_value("]"):
                self._expr()   # skip size expression
            self._s.expect_value("]")
            typ.pointer_depth += 1   # treat [] as pointer for type purposes
        node = ParamNode(typ, name)
        node.line = line
        return node

    # ── Type ───────────────────────────────────────────────────

    def _type(self) -> TypeNode:
        line = self._s.peek().line if self._s.peek() else 0
        parts: list[str] = []

        # Gather type keyword(s)
        while self._s.check_type(TokenType.KEYWORD) and self._s.peek().value in _TYPE_KEYWORDS:
            parts.append(self._s.advance().value)

        if not parts:
            tok = self._s.peek()
            raise SyntaxError(
                "expected type keyword, got " + (repr(tok.value) if tok else "EOF"), tok
            )

        # Pointer stars
        depth = 0
        while self._s.check_value("*"):
            self._s.advance()
            depth += 1

        node = TypeNode(" ".join(parts), depth)
        node.line = line
        return node

    # ── Variable declaration ───────────────────────────────────

    def _var_decl_rest(
        self, typ: TypeNode, first_name: str, name_tok: Token, top_level: bool = False
    ) -> VarDeclNode:
        declarators: list[VarDeclarator] = []
        first = self._init_declarator_rest(first_name, name_tok.line)
        declarators.append(first)

        while self._s.match_value(","):
            name_tok2 = self._s.expect_type(TokenType.IDENTIFIER)
            declarators.append(self._init_declarator_rest(name_tok2.value, name_tok2.line))

        self._s.expect_value(";")
        node = VarDeclNode(typ, declarators)
        node.line = name_tok.line
        return node

    def _init_declarator_rest(self, name: str, line: int) -> VarDeclarator:
        # Consume optional array-size brackets:  int A[10]  or  int A[m+1]
        while self._s.check_value("["):
            self._s.advance()
            if not self._s.check_value("]"):
                self._expr()          # skip size expression
            self._s.expect_value("]")
        init = None
        if self._s.match_value("="):
            init = self._expr()
        node = VarDeclarator(name, init)
        node.line = line
        return node

    # ── Block & statements ─────────────────────────────────────

    def _block(self) -> BlockNode:
        line = self._s.peek().line if self._s.peek() else 0
        self._s.expect_value("{")
        stmts: list[ASTNode] = []
        while not self._s.check_value("}") and not self._s.is_at_end():
            stmts.append(self._stmt())
        self._s.expect_value("}")
        node = BlockNode(stmts)
        node.line = line
        return node

    def _stmt(self) -> ASTNode:
        tok = self._s.peek()
        if tok is None:
            raise SyntaxError("unexpected end of file")

        # Block
        if tok.value == "{":
            return self._block()

        # Keyword-led statements
        if tok.type is TokenType.KEYWORD:
            if tok.value == "if":
                return self._if_stmt()
            if tok.value == "while":
                return self._while_stmt()
            if tok.value == "for":
                return self._for_stmt()
            if tok.value == "return":
                return self._return_stmt()
            if tok.value in ("continue", "break"):
                return self._jump_stmt()
            if tok.value in _TYPE_KEYWORDS:
                return self._var_decl_as_stmt()

        # Expression statement
        return self._expr_stmt()

    def _var_decl_as_stmt(self) -> VarDeclNode:
        typ = self._type()
        name_tok = self._s.expect_type(TokenType.IDENTIFIER)
        return self._var_decl_rest(typ, name_tok.value, name_tok)

    def _if_stmt(self) -> IfNode:
        line = self._s.peek().line
        self._s.expect_value("if")
        self._s.expect_value("(")
        cond = self._expr()
        self._s.expect_value(")")
        then_b = self._stmt()
        else_b = None
        if self._s.match_value("else"):
            else_b = self._stmt()
        node = IfNode(cond, then_b, else_b)
        node.line = line
        return node

    def _while_stmt(self) -> WhileNode:
        line = self._s.peek().line
        self._s.expect_value("while")
        self._s.expect_value("(")
        cond = self._expr()
        self._s.expect_value(")")
        body = self._stmt()
        node = WhileNode(cond, body)
        node.line = line
        return node

    def _for_stmt(self) -> ForNode:
        line = self._s.peek().line
        self._s.expect_value("for")
        self._s.expect_value("(")
        init = self._for_init()
        cond = None if self._s.check_value(";") else self._expr()
        self._s.expect_value(";")
        update = None if self._s.check_value(")") else self._expr()
        self._s.expect_value(")")
        body = self._stmt()
        node = ForNode(init, cond, update, body)
        node.line = line
        return node

    def _for_init(self) -> Optional[ASTNode]:
        if self._s.check_value(";"):
            self._s.advance()
            return None
        if self._s.check_type(TokenType.KEYWORD) and self._s.peek().value in _TYPE_KEYWORDS:
            return self._var_decl_as_stmt()
        return self._expr_stmt()

    def _jump_stmt(self) -> JumpNode:
        tok = self._s.advance()          # 'continue' or 'break'
        self._s.expect_value(";")
        node = JumpNode(tok.value)
        node.line = tok.line
        return node

    def _return_stmt(self) -> ReturnNode:
        line = self._s.peek().line
        self._s.expect_value("return")
        value = None
        if not self._s.check_value(";"):
            value = self._expr()
        self._s.expect_value(";")
        node = ReturnNode(value)
        node.line = line
        return node

    def _expr_stmt(self) -> ExprStmtNode:
        line = self._s.peek().line if self._s.peek() else 0
        expr = self._expr()
        self._s.expect_value(";")
        node = ExprStmtNode(expr)
        node.line = line
        return node

    # ── Expression hierarchy ───────────────────────────────────

    def _expr(self) -> ASTNode:
        return self._assignment()

    def _assignment(self) -> ASTNode:
        # Parse a full conditional expression first, then decide if it is
        # the left-hand side of an assignment.  This handles:
        #   x = 1        (IdentifierNode)
        #   arr[i] = 0   (IndexNode)
        #   *ptr = v     (UnaryOpNode with op='*')
        # Non-lvalues (literals, binary expressions) leave the assign op in the
        # stream so that _expr_stmt can flag INVALID_ASSIGN.
        node = self._conditional()
        op_tok = self._s.peek()
        if op_tok is not None and op_tok.value in _ASSIGN_OPS:
            if isinstance(node, (IdentifierNode, IndexNode, UnaryOpNode)):
                op = self._s.advance().value
                rhs = self._assignment()      # right-associative
                n = AssignNode(node, op, rhs)
                n.line = node.line
                return n
            # Leave op in stream — ValidatingParser._expr_stmt will flag it
        return node

    def _conditional(self) -> ASTNode:
        node = self._logical_or()
        if self._s.match_value("?"):
            line = node.line
            then_e = self._expr()
            self._s.expect_value(":")
            else_e = self._conditional()
            t = TernaryNode(node, then_e, else_e)
            t.line = line
            return t
        return node

    def _left_assoc(self, sub, *ops: str) -> ASTNode:
        node = sub()
        while (tok := self._s.match_value(*ops)):
            right = sub()
            n = BinaryOpNode(tok.value, node, right)
            n.line = node.line
            node = n
        return node

    def _logical_or(self) -> ASTNode:
        return self._left_assoc(self._logical_and, "||")

    def _logical_and(self) -> ASTNode:
        return self._left_assoc(self._equality, "&&")

    def _equality(self) -> ASTNode:
        return self._left_assoc(self._relational, "==", "!=")

    def _relational(self) -> ASTNode:
        return self._left_assoc(self._additive, "<", ">", "<=", ">=")

    def _additive(self) -> ASTNode:
        return self._left_assoc(self._multiplicative, "+", "-")

    def _multiplicative(self) -> ASTNode:
        return self._left_assoc(self._unary, "*", "/", "%")

    def _unary(self) -> ASTNode:
        tok = self._s.peek()
        if tok and tok.type is TokenType.OPERATOR and tok.value in ("+", "-", "!", "~", "&", "*"):
            op = self._s.advance()
            operand = self._unary()
            node = UnaryOpNode(op.value, operand)
            node.line = op.line
            return node
        return self._postfix()

    def _postfix(self) -> ASTNode:
        node = self._primary()
        while True:
            tok = self._s.peek()
            if tok is None:
                break
            if tok.value in ("++", "--"):
                op = self._s.advance()
                n = PostfixOpNode(node, op.value)
                n.line = op.line
                node = n
            elif tok.value == "[":
                self._s.advance()
                idx = self._expr()
                self._s.expect_value("]")
                n = IndexNode(node, idx)
                n.line = tok.line
                node = n
            elif tok.value == "(":
                # function call — callee must be an identifier
                if not isinstance(node, IdentifierNode):
                    break
                self._s.advance()
                args = self._arg_list()
                self._s.expect_value(")")
                n = CallNode(node.name, args)
                n.line = tok.line
                node = n
            else:
                break
        return node

    def _arg_list(self) -> list[ASTNode]:
        args: list[ASTNode] = []
        if self._s.check_value(")"):
            return args
        args.append(self._expr())
        while self._s.match_value(","):
            args.append(self._expr())
        return args

    def _primary(self) -> ASTNode:
        tok = self._s.peek()
        if tok is None:
            raise SyntaxError("unexpected end of file in expression")

        if tok.type is TokenType.INTEGER:
            self._s.advance()
            node = IntLiteralNode(int(tok.value.rstrip("uUlL"), 0))
            node.line = tok.line
            return node

        if tok.type is TokenType.FLOAT:
            self._s.advance()
            node = FloatLiteralNode(float(tok.value.rstrip("fFlL")))
            node.line = tok.line
            return node

        if tok.type is TokenType.STRING:
            self._s.advance()
            node = StringLiteralNode(tok.value[1:-1])   # strip quotes
            node.line = tok.line
            return node

        if tok.type is TokenType.CHAR:
            self._s.advance()
            node = CharLiteralNode(tok.value[1:-1])
            node.line = tok.line
            return node

        if tok.type is TokenType.IDENTIFIER:
            self._s.advance()
            node = IdentifierNode(tok.value)
            node.line = tok.line
            return node

        if tok.value == "(":
            self._s.advance()
            inner = self._expr()
            self._s.expect_value(")")
            return inner

        raise SyntaxError(f"unexpected token {tok.value!r}", tok)


# ─────────────────────────────────────────────────────────────
# Visitor base
# ─────────────────────────────────────────────────────────────

class Visitor:
    def generic_visit(self, node: ASTNode):
        raise NotImplementedError(f"No visitor for {type(node).__name__}")


# ─────────────────────────────────────────────────────────────
# AST pretty-printer (for debugging)
# ─────────────────────────────────────────────────────────────

class ASTPrinter(Visitor):
    def __init__(self):
        self._indent = 0

    def _line(self, text: str):
        print("  " * self._indent + text)

    def _visit_children(self, *nodes):
        self._indent += 1
        for n in nodes:
            if n is not None:
                n.accept(self)
        self._indent -= 1

    def visit_ProgramNode(self, n: ProgramNode):
        self._line("Program")
        self._visit_children(*n.declarations)

    def visit_FuncDeclNode(self, n: FuncDeclNode):
        self._line(f"FuncDecl  {n.return_type}  {n.name}()")
        self._visit_children(*n.params, n.body)

    def visit_ParamNode(self, n: ParamNode):
        self._line(f"Param  {n.type}  {n.name or '(anon)'}")

    def visit_VarDeclNode(self, n: VarDeclNode):
        self._line(f"VarDecl  {n.type}")
        self._visit_children(*n.declarators)

    def visit_VarDeclarator(self, n: VarDeclarator):
        self._line(f"Declarator  {n.name}" + (" = ..." if n.init else ""))
        if n.init:
            self._visit_children(n.init)

    def visit_BlockNode(self, n: BlockNode):
        self._line("Block")
        self._visit_children(*n.stmts)

    def visit_IfNode(self, n: IfNode):
        self._line("If")
        self._visit_children(n.condition, n.then_branch, n.else_branch)

    def visit_WhileNode(self, n: WhileNode):
        self._line("While")
        self._visit_children(n.condition, n.body)

    def visit_ForNode(self, n: ForNode):
        self._line("For")
        self._visit_children(n.init, n.condition, n.update, n.body)

    def visit_ReturnNode(self, n: ReturnNode):
        self._line("Return")
        self._visit_children(n.value)

    def visit_JumpNode(self, n: JumpNode):
        self._line(f"Jump  {n.keyword}")

    def visit_ExprStmtNode(self, n: ExprStmtNode):
        self._line("ExprStmt")
        self._visit_children(n.expr)

    def visit_AssignNode(self, n: AssignNode):
        self._line(f"Assign  {n.op}")
        self._visit_children(n.target, n.value)

    def visit_BinaryOpNode(self, n: BinaryOpNode):
        self._line(f"BinaryOp  {n.op}")
        self._visit_children(n.left, n.right)

    def visit_UnaryOpNode(self, n: UnaryOpNode):
        self._line(f"UnaryOp  {n.op}")
        self._visit_children(n.operand)

    def visit_TernaryNode(self, n: TernaryNode):
        self._line("Ternary  ?:")
        self._visit_children(n.condition, n.then_expr, n.else_expr)

    def visit_CallNode(self, n: CallNode):
        self._line(f"Call  {n.callee}()")
        self._visit_children(*n.args)

    def visit_IndexNode(self, n: IndexNode):
        self._line("Index  []")
        self._visit_children(n.array, n.index)

    def visit_PostfixOpNode(self, n: PostfixOpNode):
        self._line(f"PostfixOp  {n.op}")
        self._visit_children(n.operand)

    def visit_IdentifierNode(self, n: IdentifierNode):
        self._line(f"Identifier  {n.name}")

    def visit_IntLiteralNode(self, n: IntLiteralNode):
        self._line(f"Int  {n.value}")

    def visit_FloatLiteralNode(self, n: FloatLiteralNode):
        self._line(f"Float  {n.value}")

    def visit_StringLiteralNode(self, n: StringLiteralNode):
        self._line(f"String  {n.value!r}")

    def visit_CharLiteralNode(self, n: CharLiteralNode):
        self._line(f"Char  {n.value!r}")


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def parse_tokens(tokens: list[Token]) -> ProgramNode:
    """Parse a token list (from Phase 1) into an AST."""
    return Parser(tokens).parse()


def parse_file(filename: str) -> ProgramNode:
    """Lex + parse a C source file, returning the AST root."""
    tokens = tokenize_file(filename)
    return parse_tokens(tokens)


def parse_string(source: str) -> ProgramNode:
    """Lex + parse a C source string, returning the AST root."""
    tokens = tokenize_string(source)
    return parse_tokens(tokens)


# ─────────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    sample = r"""
int add(int a, int b) {
    return a + b;
}

int main(int argc, char *argv[]) {
    int x = 10, y = 20;
    int z;
    z = add(x, y);

    if (z > 25) {
        printf("big: %d\n", z);
    } else {
        printf("small\n");
    }

    int i;
    for (i = 0; i < 10; i++) {
        z += i;
    }

    while (z > 0) {
        z = z - 1;
    }

    return 0;
}
"""

    source = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        ast = parse_file(source) if source else parse_string(sample)
        ASTPrinter().visit_ProgramNode(ast)
    except SyntaxError as e:
        print(f"\n{e}")
        sys.exit(1)
