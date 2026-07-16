"""Gate Engine — hard-constraint gate checking with L1/L2/L3 retry strategy.

Spec §5.1:
  L1: auto-fix + retry (max 2 times)
  L2: analyze + fix + retry (max 1 time), fail → WAIT_USER
  L3: immediate WAIT_USER
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from ede.models import GateResult


class GateLevel(Enum):
    L1 = 1  # Auto-fixable: lint, format
    L2 = 2  # May be auto-fixable: test failures
    L3 = 3  # Needs human: coverage threshold, design review


@dataclass
class Gate:
    """A single gate definition."""
    name: str
    level: GateLevel
    check: Callable[[], GateResult]  # synchronous check function
    fix: Optional[Callable[[], bool]] = None  # optional auto-fix function
    max_retries: int = 0  # set from level by GateEngine


class GateEngine:
    """Checks gates and manages retry logic based on gate level.

    Usage:
        engine = GateEngine()
        engine.register(Gate("lint", GateLevel.L1, check_lint, fix=auto_lint))
        result = engine.run_gate("lint")
    """

    def __init__(self):
        self._gates: dict[str, Gate] = {}

    def register(self, gate: Gate) -> None:
        """Register a named gate."""
        # Set max_retries from level if not explicitly set
        if gate.max_retries == 0:
            gate.max_retries = {GateLevel.L1: 2, GateLevel.L2: 1, GateLevel.L3: 0}[gate.level]
        self._gates[gate.name] = gate

    def run_gate(self, name: str) -> GateResult:
        """Run a single gate with retry logic. Returns final result."""
        gate = self._gates[name]
        return self._run_with_retry(gate)

    def run_gates(self, names: list[str]) -> list[GateResult]:
        """Run multiple gates sequentially. Returns all results."""
        return [self.run_gate(n) for n in names]

    def _run_with_retry(self, gate: Gate) -> GateResult:
        attempt = 0
        last_result: Optional[GateResult] = None

        while attempt <= gate.max_retries:
            attempt += 1
            last_result = gate.check()

            if last_result.passed:
                return last_result

            # Gate failed — try auto-fix if available
            if gate.fix is not None and attempt <= gate.max_retries:
                fixed = gate.fix()
                if not fixed:
                    # Fix failed, stop retrying
                    break

        # All retries exhausted — return final result
        if last_result is not None:
            last_result.detail += f" (attempts: {attempt})"
        return last_result or GateResult(
            task_id="",
            gate_name=gate.name,
            passed=False,
            detail=f"No result after {attempt} attempts",
        )

    # ── Convenience: built-in gates for MVP ──────────

    @staticmethod
    def make_lint_gate(check_fn: Callable, fix_fn: Optional[Callable] = None) -> Gate:
        return Gate("lint", GateLevel.L1, check_fn, fix=fix_fn)

    @staticmethod
    def make_test_gate(check_fn: Callable, fix_fn: Optional[Callable] = None) -> Gate:
        return Gate("test", GateLevel.L2, check_fn, fix=fix_fn)

    @staticmethod
    def make_coverage_gate(check_fn: Callable) -> Gate:
        return Gate("coverage", GateLevel.L3, check_fn)
