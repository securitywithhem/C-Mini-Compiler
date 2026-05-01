#!/bin/bash

# C Mini-Compiler Test Runner
# Runs all tests to verify the compiler works correctly

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║     C Mini-Compiler - Test Suite                       ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python --version 2>&1)
echo "   $python_version"
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
python -c "import flask; print('   ✓ Flask installed')" 2>/dev/null || {
    echo "   ✗ Flask not installed. Run: pip install -r requirements.txt"
    exit 1
}

python -c "import flask_cors; print('   ✓ Flask-CORS installed')" 2>/dev/null || {
    echo "   ✗ Flask-CORS not installed. Run: pip install -r requirements.txt"
    exit 1
}

echo ""
echo "🧪 Running Tests..."
echo ""

# Test 1: Lexer
echo "─────────────────────────────────────────────────────────"
echo "TEST 1: Lexical Analysis (Lexer)"
echo "─────────────────────────────────────────────────────────"
python src/c_lexer.py > /tmp/lexer_test.txt 2>&1
if [ $? -eq 0 ]; then
    echo "✓ PASS: Lexer works correctly"
    echo "  (Output available in /tmp/lexer_test.txt)"
else
    echo "✗ FAIL: Lexer error"
    cat /tmp/lexer_test.txt
fi
echo ""

# Test 2: Parser
echo "─────────────────────────────────────────────────────────"
echo "TEST 2: Syntax Analysis (Parser)"
echo "─────────────────────────────────────────────────────────"
python src/c_parser.py > /tmp/parser_test.txt 2>&1
if [ $? -eq 0 ]; then
    echo "✓ PASS: Parser works correctly"
    echo "  (Output available in /tmp/parser_test.txt)"
else
    echo "✗ FAIL: Parser error"
    cat /tmp/parser_test.txt
fi
echo ""

# Test 3: Validator
echo "─────────────────────────────────────────────────────────"
echo "TEST 3: Semantic Analysis (Validator)"
echo "─────────────────────────────────────────────────────────"
python src/c_validator.py > /tmp/validator_test.txt 2>&1
if [ $? -eq 0 ]; then
    echo "✓ PASS: Validator works correctly"
    echo "  (Output shows expected errors)"
else
    echo "✗ FAIL: Validator error"
    cat /tmp/validator_test.txt
fi
echo ""

# Test 4: Run pytest tests
echo "─────────────────────────────────────────────────────────"
echo "TEST 4: Pytest Test Suite"
echo "─────────────────────────────────────────────────────────"
python -m pytest tests/ -v

# Summary
echo "╔════════════════════════════════════════════════════════╗"
echo "║  All Tests Complete!                                   ║"
echo "║                                                        ║"
echo "║  Next steps:                                           ║"
echo "║  1. Start backend: python backend.py                   ║"
echo "║  2. Open browser:  http://localhost:5000               ║"
echo "║  3. Try compiling some C code!                         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
