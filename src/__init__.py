"""
C Mini-Compiler — package root.

Five-phase compilation pipeline:

    1. Lexer        →  tokens             (lexer.py)
    2. Parser       →  AST                (parser.py)
    3. Validator    →  syntax errors      (validator.py)
    4. Semantic     →  semantic errors    (symbol_table.py + semantic.py)
    5. Reporter     →  unified output     (error_handler.py)

Convenience entry point::

    >>> from src import compile_source
    >>> text, exit_code = compile_source(open("file.c").read())
"""

from .lexer         import Token, TokenType, tokenize_string, tokenize_file
from .parser        import ProgramNode, parse_string, parse_file
from .validator     import validate_string, validate_file, Diagnostic, ErrorKind
from .symbol_table  import SymbolTable, VariableEntry, FunctionEntry, ParamInfo
from .semantic      import analyze_string, analyze_file, SemanticError, SemanticErrorKind
from .error_handler import collect_errors, report_string, report_file, UnifiedError
from .compiler      import compile_source, compile_file

__all__ = [
    # lexer
    "Token", "TokenType", "tokenize_string", "tokenize_file",
    # parser
    "ProgramNode", "parse_string", "parse_file",
    # validator
    "validate_string", "validate_file", "Diagnostic", "ErrorKind",
    # symbol table
    "SymbolTable", "VariableEntry", "FunctionEntry", "ParamInfo",
    # semantic
    "analyze_string", "analyze_file", "SemanticError", "SemanticErrorKind",
    # reporter
    "collect_errors", "report_string", "report_file", "UnifiedError",
    # driver
    "compile_source", "compile_file",
]

__version__ = "1.0.0"
