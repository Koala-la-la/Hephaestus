"""Unit tests for Gate Engine — L1/L2/L3 retry logic."""

import sys
sys.path.insert(0, r"C:\obsidian\KB\weiwei")

from ede.gate_engine import GateEngine, Gate, GateLevel
from ede.models import GateResult


def _make_result(passed: bool, detail: str = "") -> GateResult:
    return GateResult(task_id="t1", gate_name="test", passed=passed, detail=detail)


def test_l1_retries_twice_then_passes():
    """L1 gate retries up to 2 times after fix."""
    calls = []
    def check():
        calls.append("check")
        return _make_result(len(calls) >= 3)

    def fix():
        return True

    engine = GateEngine()
    engine.register(Gate("lint", GateLevel.L1, check, fix=fix))
    result = engine.run_gate("lint")
    assert result.passed
    assert len(calls) == 3  # initial + 2 retries


def test_l1_retries_exhausted():
    """L1 gate fails after 3 attempts (initial + 2 retries)."""
    calls = []
    def check():
        calls.append("check")
        return _make_result(False)
    def fix():
        return True

    engine = GateEngine()
    engine.register(Gate("lint", GateLevel.L1, check, fix=fix))
    result = engine.run_gate("lint")
    assert not result.passed
    assert len(calls) == 3


def test_l2_retries_once():
    """L2 gate retries at most 1 time."""
    calls = []
    def check():
        calls.append("check")
        return _make_result(len(calls) >= 2)
    def fix():
        return True

    engine = GateEngine()
    engine.register(Gate("test", GateLevel.L2, check, fix=fix))
    result = engine.run_gate("test")
    assert result.passed
    assert len(calls) == 2


def test_l2_exhausted():
    """L2 gate fails after 2 attempts."""
    calls = []
    def check():
        calls.append("check")
        return _make_result(False)
    def fix():
        return True

    engine = GateEngine()
    engine.register(Gate("test", GateLevel.L2, check, fix=fix))
    result = engine.run_gate("test")
    assert not result.passed
    assert len(calls) == 2


def test_l3_no_retry():
    """L3 gate runs once, never retries, has no fix."""
    calls = []
    def check():
        calls.append("check")
        return _make_result(False)
    engine = GateEngine()
    engine.register(Gate("coverage", GateLevel.L3, check))
    result = engine.run_gate("coverage")
    assert not result.passed
    assert len(calls) == 1


def test_pass_on_first_try():
    """Gate that passes immediately runs exactly once."""
    calls = []
    def check():
        calls.append("check")
        return _make_result(True)
    engine = GateEngine()
    engine.register(Gate("fast", GateLevel.L1, check))
    result = engine.run_gate("fast")
    assert result.passed
    assert len(calls) == 1
