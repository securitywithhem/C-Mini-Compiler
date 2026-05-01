/*
 * Edge-case sample — exercises every category of error the compiler
 * detects, in a single file. Run:
 *      python main.py samples/edge_cases.c
 *
 * Expected diagnostics:
 *   - undeclared variable
 *   - divide by zero
 *   - multiple declaration
 *   - argument mismatch
 *   - undeclared function
 *   - missing return (in non-void function)
 */

int add(int a, int b) {
    return a + b;
}

int compute() {
    int x = undeclared_var + 5;     /* UNDECLARED_VARIABLE */
    int z = 100 / 0;                /* DIVIDE_BY_ZERO */

    int dup = 1;
    int dup = 2;                    /* MULTIPLE_DECLARATION */

    int r = add(1, 2, 3);           /* ARGUMENT_MISMATCH (expects 2) */
    int q = mystery(42);            /* UNDECLARED_FUNCTION */
    /* MISSING_RETURN — function declared int but no return */
}

int main() {
    return 0;
}
