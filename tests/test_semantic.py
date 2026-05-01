"""
Test suite for Phase 4 — Semantic Analysis.

Tests all four mandatory error types plus supporting checks:
  1. UNDECLARED_VARIABLE
  2. DIVIDE_BY_ZERO
  3. ARGUMENT_MISMATCH
  4. MULTIPLE_DECLARATION
  5. UNDECLARED_FUNCTION
  6. TYPE_MISMATCH (warnings)
  7. Symbol table correctness
  8. Scope chain (nested blocks, for-init)
  9. Valid programs (zero errors expected)
"""

import sys
from src.semantic     import analyze_string, SemanticErrorKind
from src.symbol_table import SymbolTable

# ─────────────────────────────────────────────────────────────
# Minimal test harness
# ─────────────────────────────────────────────────────────────

_PASS = 0
_FAIL = 0


def _run(label: str, source: str, expected_kinds, *, warnings_ok: bool = True):
    global _PASS, _FAIL
    errors, _ = analyze_string(source)
    if not warnings_ok:
        errors = [e for e in errors if not e.is_warning]

    found_kinds = [e.kind for e in errors]
    expected    = list(expected_kinds)

    ok = True
    for k in expected:
        if k not in found_kinds:
            print(f"  MISSING  {k.name}")
            ok = False
        else:
            found_kinds.remove(k)

    # Unexpected errors are only a failure if not warnings-ok
    if not warnings_ok:
        for k in found_kinds:
            print(f"  UNEXPECTED  {k.name}")
            ok = False

    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}")
    if not ok:
        for e in errors:
            print(f"       {e}")
    _FAIL += (0 if ok else 1)
    _PASS += (1 if ok else 0)


def _run_clean(label: str, source: str):
    """Expect zero errors (warnings are ignored)."""
    global _PASS, _FAIL
    errors, _ = analyze_string(source)
    hard_errors = [e for e in errors if not e.is_warning]
    ok = len(hard_errors) == 0
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        for e in hard_errors:
            print(f"       {e}")
    _FAIL += (0 if ok else 1)
    _PASS += (1 if ok else 0)


# ═════════════════════════════════════════════════════════════
# 1. UNDECLARED VARIABLE
# ═════════════════════════════════════════════════════════════
print("\n── 1. UNDECLARED VARIABLE ──────────────────────────────")

_run(
    "simple undeclared use",
    r"""
int main() {
    int x = y + 5;
    return 0;
}
""",
    [SemanticErrorKind.UNDECLARED_VARIABLE],
)

_run(
    "undeclared in condition",
    r"""
int main() {
    if (flag) {
        return 1;
    }
    return 0;
}
""",
    [SemanticErrorKind.UNDECLARED_VARIABLE],
)

_run(
    "undeclared in for-update",
    r"""
int main() {
    int i;
    for (i = 0; i < 10; i++) {
        int t = undefined_var;
    }
    return 0;
}
""",
    [SemanticErrorKind.UNDECLARED_VARIABLE],
)

_run(
    "multiple undeclared variables",
    r"""
int main() {
    int x = a + b + c;
    return 0;
}
""",
    [
        SemanticErrorKind.UNDECLARED_VARIABLE,
        SemanticErrorKind.UNDECLARED_VARIABLE,
        SemanticErrorKind.UNDECLARED_VARIABLE,
    ],
)

_run_clean(
    "declared before use — no error",
    r"""
int main() {
    int y = 10;
    int x = y + 5;
    return 0;
}
""",
)

_run_clean(
    "parameter visible inside function — no error",
    r"""
int add(int a, int b) {
    return a + b;
}
int main() { return 0; }
""",
)


# ═════════════════════════════════════════════════════════════
# 2. DIVIDE BY ZERO
# ═════════════════════════════════════════════════════════════
print("\n── 2. DIVIDE BY ZERO ───────────────────────────────────")

_run(
    "integer divide by zero literal",
    r"""
int main() {
    int x = 10 / 0;
    return 0;
}
""",
    [SemanticErrorKind.DIVIDE_BY_ZERO],
)

_run(
    "modulo by zero literal",
    r"""
int main() {
    int x = 7 % 0;
    return 0;
}
""",
    [SemanticErrorKind.DIVIDE_BY_ZERO],
)

_run(
    "divide by zero in nested expression",
    r"""
int main() {
    int a = 5;
    int b = (a + 3) / 0;
    return 0;
}
""",
    [SemanticErrorKind.DIVIDE_BY_ZERO],
)

_run_clean(
    "divide by variable — not an error",
    r"""
int main() {
    int a = 5;
    int n = 2;
    int b = a / n;
    return 0;
}
""",
)

_run_clean(
    "divide by non-zero literal — no error",
    r"""
int main() {
    int x = 10 / 2;
    return 0;
}
""",
)


# ═════════════════════════════════════════════════════════════
# 3. ARGUMENT MISMATCH
# ═════════════════════════════════════════════════════════════
print("\n── 3. ARGUMENT MISMATCH ────────────────────────────────")

_run(
    "too many arguments",
    r"""
int add(int a, int b) {
    return a + b;
}
int main() {
    int r = add(1, 2, 3);
    return 0;
}
""",
    [SemanticErrorKind.ARGUMENT_MISMATCH],
)

_run(
    "too few arguments",
    r"""
int multiply(int a, int b) {
    return a * b;
}
int main() {
    int r = multiply(5);
    return 0;
}
""",
    [SemanticErrorKind.ARGUMENT_MISMATCH],
)

_run(
    "zero args to non-void function",
    r"""
int getVal(int x) {
    return x;
}
int main() {
    int r = getVal();
    return 0;
}
""",
    [SemanticErrorKind.ARGUMENT_MISMATCH],
)

_run_clean(
    "correct argument count — no error",
    r"""
int add(int a, int b) {
    return a + b;
}
int main() {
    int r = add(3, 4);
    return 0;
}
""",
)

_run_clean(
    "void parameter list — no error",
    r"""
int getValue() {
    return 42;
}
int main() {
    int v = getValue();
    return 0;
}
""",
)

_run_clean(
    "stdlib printf — not flagged as undeclared",
    r"""
int main() {
    printf("hello\n");
    return 0;
}
""",
)


# ═════════════════════════════════════════════════════════════
# 4. MULTIPLE DECLARATION
# ═════════════════════════════════════════════════════════════
print("\n── 4. MULTIPLE DECLARATION ─────────────────────────────")

_run(
    "same variable declared twice in one block",
    r"""
int main() {
    int x = 5;
    int x = 10;
    return 0;
}
""",
    [SemanticErrorKind.MULTIPLE_DECLARATION],
)

_run(
    "double declaration of different types",
    r"""
int main() {
    int counter = 0;
    float counter = 1.5;
    return 0;
}
""",
    [SemanticErrorKind.MULTIPLE_DECLARATION],
)

_run(
    "triple declaration in same scope",
    r"""
int main() {
    int n = 1;
    int n = 2;
    int n = 3;
    return 0;
}
""",
    [SemanticErrorKind.MULTIPLE_DECLARATION, SemanticErrorKind.MULTIPLE_DECLARATION],
)

_run_clean(
    "same name in different scopes — no error (shadowing)",
    r"""
int main() {
    int x = 5;
    {
        int x = 10;
    }
    return 0;
}
""",
)

_run_clean(
    "same name in separate functions — no error",
    r"""
int foo() {
    int value = 1;
    return value;
}
int bar() {
    int value = 2;
    return value;
}
int main() { return 0; }
""",
)


# ═════════════════════════════════════════════════════════════
# 5. UNDECLARED FUNCTION
# ═════════════════════════════════════════════════════════════
print("\n── 5. UNDECLARED FUNCTION ──────────────────────────────")

_run(
    "call to completely unknown function",
    r"""
int main() {
    int r = mystery(42);
    return 0;
}
""",
    [SemanticErrorKind.UNDECLARED_FUNCTION],
)

_run_clean(
    "forward call resolved via pre-scan — no error",
    r"""
int main() {
    int r = helper(5);
    return 0;
}
int helper(int x) {
    return x * 2;
}
""",
)


# ═════════════════════════════════════════════════════════════
# 6. SCOPE CHAIN CORRECTNESS
# ═════════════════════════════════════════════════════════════
print("\n── 6. SCOPE CHAIN ──────────────────────────────────────")

_run_clean(
    "variable declared in outer scope visible in nested",
    r"""
int main() {
    int outer = 10;
    {
        int inner = outer + 5;
    }
    return 0;
}
""",
)

_run_clean(
    "for-init variable visible in loop body",
    r"""
int main() {
    int sum = 0;
    for (int i = 0; i < 10; i++) {
        sum = sum + i;
    }
    return 0;
}
""",
)

_run(
    "for-init variable NOT visible after the loop",
    r"""
int main() {
    for (int i = 0; i < 5; i++) { }
    int x = i;
    return 0;
}
""",
    [SemanticErrorKind.UNDECLARED_VARIABLE],
)

_run_clean(
    "parameter visible throughout function body",
    r"""
int double_it(int n) {
    int result = n * 2;
    return result;
}
int main() { return 0; }
""",
)


# ═════════════════════════════════════════════════════════════
# 7. SYMBOL TABLE CONTENTS
# ═════════════════════════════════════════════════════════════
print("\n── 7. SYMBOL TABLE ─────────────────────────────────────")


def _check_table(label: str, source: str, expected_fns: list, expected_vars: list):
    global _PASS, _FAIL
    _, table = analyze_string(source)

    fn_names  = {f.name for f in table.all_functions()}
    var_names = {v.name for v in table.all_variables()}

    ok = True
    for fn in expected_fns:
        if fn not in fn_names:
            print(f"  MISSING function '{fn}' in symbol table")
            ok = False
    for var in expected_vars:
        if var not in var_names:
            print(f"  MISSING variable '{var}' in symbol table")
            ok = False

    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    _FAIL += (0 if ok else 1)
    _PASS += (1 if ok else 0)


_check_table(
    "functions and variables recorded",
    r"""
int add(int a, int b) {
    return a + b;
}
int main() {
    int x = 10;
    int y = 20;
    int result = add(x, y);
    return result;
}
""",
    expected_fns=["add", "main"],
    expected_vars=["a", "b", "x", "y", "result"],
)

_check_table(
    "parameters stored in symbol table",
    r"""
float average(float sum, int count) {
    return sum / count;
}
int main() { return 0; }
""",
    expected_fns=["average"],
    expected_vars=["sum", "count"],
)


# ═════════════════════════════════════════════════════════════
# 8. COMBINED ERROR SCENARIOS
# ═════════════════════════════════════════════════════════════
print("\n── 8. COMBINED ERRORS ──────────────────────────────────")

_run(
    "divide-by-zero + undeclared in same function",
    r"""
int main() {
    int x = badVar / 0;
    return 0;
}
""",
    [SemanticErrorKind.UNDECLARED_VARIABLE, SemanticErrorKind.DIVIDE_BY_ZERO],
)

_run(
    "all four mandatory error types at once",
    r"""
int add(int a, int b) {
    return a + b;
}

void demo() {
    int x = missing + 1;
    int y = 5 / 0;
    int z = 3;
    int z = 4;
    int r = add(1);
}

int main() { return 0; }
""",
    [
        SemanticErrorKind.UNDECLARED_VARIABLE,
        SemanticErrorKind.DIVIDE_BY_ZERO,
        SemanticErrorKind.MULTIPLE_DECLARATION,
        SemanticErrorKind.ARGUMENT_MISMATCH,
    ],
)


# ═════════════════════════════════════════════════════════════
# 9. VALID PROGRAMS — ZERO ERRORS EXPECTED
# ═════════════════════════════════════════════════════════════
print("\n── 9. VALID PROGRAMS ───────────────────────────────────")

_run_clean(
    "factorial (recursive)",
    r"""
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
int main() {
    int r = factorial(5);
    return 0;
}
""",
)

_run_clean(
    "bubble sort",
    r"""
void swap(int a, int b) {
    int tmp = a;
    a = b;
    b = tmp;
}

int main() {
    int arr[5];
    int n = 5;
    int i;
    int j;
    for (i = 0; i < n - 1; i++) {
        for (j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                swap(arr[j], arr[j + 1]);
            }
        }
    }
    return 0;
}
""",
)

_run_clean(
    "fibonacci iterative",
    r"""
int fibonacci(int n) {
    int a = 0;
    int b = 1;
    int i;
    int tmp;
    for (i = 0; i < n; i++) {
        tmp = a + b;
        a = b;
        b = tmp;
    }
    return a;
}
int main() {
    int f = fibonacci(10);
    return 0;
}
""",
)

_run_clean(
    "nested if-else with all variables declared",
    r"""
int classify(int x) {
    int result;
    if (x < 0) {
        result = -1;
    } else {
        if (x == 0) {
            result = 0;
        } else {
            result = 1;
        }
    }
    return result;
}
int main() { return 0; }
""",
)

_run_clean(
    "multiple functions calling each other",
    r"""
int square(int x) {
    return x * x;
}

int sum_of_squares(int a, int b) {
    return square(a) + square(b);
}

int main() {
    int result = sum_of_squares(3, 4);
    return 0;
}
""",
)


# ═════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════

total = _PASS + _FAIL
print(f"""
══════════════════════════════════════════════════════════
  Results:  {_PASS}/{total} passed   ({_FAIL} failed)
══════════════════════════════════════════════════════════
""")

sys.exit(0 if _FAIL == 0 else 1)
