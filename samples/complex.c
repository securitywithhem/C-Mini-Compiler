/*
 * Complex valid C program — exercises every supported feature:
 * recursion, multiple functions, control flow, array indexing,
 * loops, and pointer/string arguments.
 */
#include <stdio.h>

int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

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

int sum_array(int n) {
    int arr[10];
    int total = 0;
    int i;
    for (i = 0; i < n; i = i + 1) {
        arr[i] = i * i;
        total = total + arr[i];
    }
    return total;
}

int main() {
    int fact   = factorial(5);
    int fib    = fibonacci(10);
    int sumsq  = sum_array(5);

    if (fact > fib) {
        printf("factorial wins: %d\n", fact);
    } else {
        printf("fibonacci wins: %d\n", fib);
    }

    return sumsq;
}
