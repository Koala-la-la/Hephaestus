"""Gate Engine — hard-constraint gate checking with L1/L2/L3 retry strategy.

Spec §5.1:
  L1: auto-fix + retry (max 2 times)
  L2: analyze + fix + retry (max 1 time), fail → WAIT_USER
  L3: immediate WAIT_USER

v0.3: Async gate checks (spec C-006). Gate.check/fix are now async.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Awaitable

from ede.models import GateResult


class GateLevel(Enum):
    L1 = 1  # Auto-fixable: lint, format
    L2 = 2  # May be auto-fixable: test failures
    L3 = 3  # Needs human: coverage threshold, design review


@dataclass
class Gate:
    """A single gate definition (async)."""
    name: str
    level: GateLevel
    check: Callable[[], Awaitable[GateResult]]  # async check function
    fix: Optional[Callable[[], Awaitable[bool]]] = None  # optional async auto-fix
    max_retries: int = 0
    blocking: bool = True  # False = informational only, never blocks (spec §6.1)


class GateEngine:
    """Checks gates and manages retry logic based on gate level (async)."""

    def __init__(self):
        self._gates: dict[str, Gate] = {}

    def register(self, gate: Gate) -> None:
        """Register a named gate."""
        if gate.max_retries == 0:
            gate.max_retries = {GateLevel.L1: 2, GateLevel.L2: 1, GateLevel.L3: 0}[gate.level]
        self._gates[gate.name] = gate

    async def run_gate(self, name: str) -> GateResult:
        """Run a single gate with retry logic. Returns final result."""
        gate = self._gates[name]
        return await self._run_with_retry(gate)

    async def run_gates(self, names: list[str]) -> list[GateResult]:
        """Run multiple gates concurrently. Returns all results."""
        return await asyncio.gather(*[self.run_gate(n) for n in names])

    async def _run_with_retry(self, gate: Gate) -> GateResult:
        attempt = 0
        last_result: Optional[GateResult] = None

        while attempt <= gate.max_retries:
            attempt += 1
            last_result = await gate.check()

            if last_result.passed:
                return last_result

            if gate.fix is not None and attempt <= gate.max_retries:
                fixed = await gate.fix()
                if not fixed:
                    break

        if last_result is not None:
            last_result.detail += f" (attempts: {attempt})"
        return last_result or GateResult(
            task_id="",
            gate_name=gate.name,
            passed=False,
            detail=f"No result after {attempt} attempts",
        )

    @staticmethod
    def make_lint_gate(check_fn: Callable, fix_fn: Optional[Callable] = None) -> Gate:
        return Gate("lint", GateLevel.L1, check_fn, fix=fix_fn)

    @staticmethod
    def make_test_gate(check_fn: Callable, fix_fn: Optional[Callable] = None) -> Gate:
        return Gate("test", GateLevel.L2, check_fn, fix=fix_fn)

    @staticmethod
    def make_coverage_gate(check_fn: Callable) -> Gate:
        return Gate("coverage", GateLevel.L3, check_fn)
