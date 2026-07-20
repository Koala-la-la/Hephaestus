"""Built-in gates for the EDE pipeline."""

from ede.gates.builtin import (
    make_lint_gate,
    make_test_gate,
    make_coverage_gate,
    register_builtin_gates,
)

__all__ = [
    "make_lint_gate",
    "make_test_gate",
    "make_coverage_gate",
    "register_builtin_gates",
]
