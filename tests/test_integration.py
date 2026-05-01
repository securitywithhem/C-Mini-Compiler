"""
End-to-end test suite for the C Mini-Compiler — Phase 5.

Tests every requirement category through the *unified* reporter
(c_reporter.collect_errors), so a passing test confirms the entire
pipeline is wired up correctly: lexer → parser → validator → semantic
analyzer → reporter.

Test categories
---------------
  A. UNDECLARED VARIABLES         (3 tests)
  B. INVALID OPERATIONS           (3 tests)
  C. FUNCTION CALLS               (3 tests)
  D. MULTIPLE DECLARATIONS        (3 tests)
  E. VALID CODE — zero errors     (3 tests)

Each test is a tuple of:
    (label, source, expected_kinds_present)

`expected_kinds_present` is the *minimum* set of kinds that must appear.
Extra warnings are tolerated; unexpected hard errors fail the test.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Iterable

from src.error_handler import collect_errors, report_string, UnifiedError


# ─────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    category:        str
    label:           str
    source:          str
    expected_kinds:  list[str]    # kinds (by name) that must appear
    expect_clean:    bool = False  # True → expect zero hard errors


def _run_one(t: TestCase) -> tuple[bool, list[str]]:
    """Return (passed, failure_messages)."""
    errors, _ = collect_errors(t.source)
    found_kinds  = [e.kind for e in errors]
    hard_errors  = [e for e in errors if e.severity == "error"]
    failures: list[str] = []

    if t.expect_clean:
        if hard_errors:
            failures.append(
                f"expected zero errors, got {len(hard_errors)}: "
                + ", ".join(e.kind for e in hard_errors)
            )
        return (not failures, failures)

    # Each expected kind must occur (counts duplicates correctly)
    remaining = list(found_kinds)
    for k in t.expected_kinds:
        if k in remaining:
            remaining.remove(k)
        else:
            failures.append(f"missing expected error kind '{k}'")

    return (not failures, failures)


def _print_test(idx: int, total: int, t: TestCase, ok: bool, fails: list[str]):
    status = "\033[32mPASS\033[0m" if ok else "\033[31mFAIL\033[0m"
    print(f"  [{idx:>2}/{total}] [{status}] {t.label}")
    if not ok:
        for f in fails:
            print(f"           ↳ {f}")


# ─────────────────────────────────────────────────────────────
# Test cases
# ─────────────────────────────────────────────────────────────

CATEGORY_A: list[TestCase] = [
    TestCase(
        "A", "1a. Simple undeclared variable",
        r"""
int main() {
    x = 10;
    return 0;
}
""",
        ["UNDECLARED_VARIABLE"],
    ),
    TestCase(
        "A", "1b. Undeclared variable inside expression",
        r"""
int main() {
    int x = y + 5 * z;
    return 0;
}
""",
        ["UNDECLARED_VARIABLE", "UNDECLARED_VARIABLE"],
    ),
    TestCase(
        "A", "1c. Undeclared variable referenced inside function body",
        r"""
int compute(int a) {
    return a + missing_param;
}
int main() {
    return compute(1);
}
""",
        ["UNDECLARED_VARIABLE"],
    ),
]

CATEGORY_B: list[TestCase] = [
    TestCase(
        "B", "2a. Division by zero literal",
        r"""
int main() {
    int x = 100 / 0;
    return 0;
}
""",
        ["DIVIDE_BY_ZERO"],
    ),
    TestCase(
        "B", "2b. Modulo by zero literal",
        r"""
int main() {
    int r = 25 % 0;
    return 0;
}
""",
        ["DIVIDE_BY_ZERO"],
    ),
    TestCase(
        "B", "2c. Type mismatch on arithmetic operands (string)",
        r"""
int main() {
    int x = "hello" - "world";
    return 0;
}
""",
        ["TYPE_MISMATCH"],
    ),
]

CATEGORY_C: list[TestCase] = [
    TestCase(
        "C", "3a. Wrong argument count (too many)",
        r"""
int add(int a, int b) {
    return a + b;
}
int main() {
    return add(1, 2, 3);
}
""",
        ["ARGUMENT_MISMATCH"],
    ),
    TestCase(
        "C", "3b. Wrong argument types (incompatible pointer/value)",
        r"""
int needs_int(int n) {
    return n + 1;
}
int main() {
    int r = needs_int("hello");
    return r;
}
""",
        ["TYPE_MISMATCH"],
    ),
    TestCase(
        "C", "3c. Calling undeclared function",
        r"""
int main() {
    int r = unknown_function(42);
    return 0;
}
""",
        ["UNDECLARED_FUNCTION"],
    ),
]

CATEGORY_D: list[TestCase] = [
    TestCase(
        "D", "4a. Duplicate variable in same (function) scope",
        r"""
int main() {
    int x = 1;
    int x = 2;
    return 0;
}
""",
        ["MULTIPLE_DECLARATION"],
    ),
    TestCase(
        "D", "4b. Multiple global variable declarations",
        r"""
int counter = 0;
int counter = 1;

int main() {
    return counter;
}
""",
        ["MULTIPLE_DECLARATION"],
    ),
    TestCase(
        "D", "4c. Duplicate inside the same nested block",
        r"""
int main() {
    int outer = 0;
    {
        int n = 1;
        int n = 2;
    }
    return outer;
}
""",
        ["MULTIPLE_DECLARATION"],
    ),
]

CATEGORY_E: list[TestCase] = [
    TestCase(
        "E", "5a. Simple valid program",
        r"""
int main() {
    int x = 5;
    int y = 10;
    int sum = x + y;
    return sum;
}
""",
        [], expect_clean=True,
    ),
    TestCase(
        "E", "5b. Multiple functions calling one another",
        r"""
int square(int n) {
    return n * n;
}
int sum_of_squares(int a, int b) {
    return square(a) + square(b);
}
int main() {
    return sum_of_squares(3, 4);
}
""",
        [], expect_clean=True,
    ),
    TestCase(
        "E", "5c. Complex expressions, loops, and conditions",
        r"""
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

int main() {
    int total = 0;
    int i;
    for (i = 1; i <= 5; i = i + 1) {
        total = total + factorial(i);
    }
    if (total > 100) {
        total = total / 2;
    } else {
        total = total * 2;
    }
    return total;
}
""",
        [], expect_clean=True,
    ),
]

ALL_CATEGORIES: list[tuple[str, str, list[TestCase]]] = [
    ("A", "UNDECLARED VARIABLES",   CATEGORY_A),
    ("B", "INVALID OPERATIONS",     CATEGORY_B),
    ("C", "FUNCTION CALLS",         CATEGORY_C),
    ("D", "MULTIPLE DECLARATIONS",  CATEGORY_D),
    ("E", "VALID CODE",             CATEGORY_E),
]


# ─────────────────────────────────────────────────────────────
# Demo: show the reporter output for one mixed-error sample
# ─────────────────────────────────────────────────────────────

_DEMO_SOURCE = r"""
int add(int a, int b) {
    return a + b;
}

int main() {
    int x = y + 5;          /* undeclared 'y' */
    int z = 10 / 0;         /* divide by zero */
    int dup = 1;
    int dup = 2;            /* duplicate declaration */
    int r = add(1, 2, 3);   /* argument mismatch */
    return 0;
}
"""


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main() -> int:
    print("\n" + "═" * 64)
    print("  C MINI-COMPILER — END-TO-END TEST SUITE")
    print("═" * 64)

    total_pass = 0
    total_fail = 0
    cat_summary: list[tuple[str, int, int]] = []

    for code, title, tests in ALL_CATEGORIES:
        print(f"\n── Category {code}: {title} ──")
        cat_pass = 0
        cat_fail = 0
        for i, t in enumerate(tests, start=1):
            ok, fails = _run_one(t)
            _print_test(i, len(tests), t, ok, fails)
            if ok:
                cat_pass += 1
                total_pass += 1
            else:
                cat_fail += 1
                total_fail += 1
        cat_summary.append((f"{code} — {title}", cat_pass, len(tests)))

    # Final summary table
    print("\n" + "═" * 64)
    print("  SUMMARY")
    print("═" * 64)
    for label, p, t in cat_summary:
        bar = "█" * p + "·" * (t - p)
        print(f"  {label:<35} {bar}  {p}/{t}")
    print("─" * 64)
    print(f"  TOTAL: {total_pass}/{total_pass + total_fail} passed, {total_fail} failed")
    print("═" * 64)

    # Demo a real reporter run on a mixed-error sample
    print("\n── DEMO: console reporter on a mixed-error sample ──\n")
    text, exit_code = report_string(
        _DEMO_SOURCE, fmt="console", color=True, file_name="demo.c"
    )
    print(text)
    print(f"(reporter exit code: {exit_code})")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
