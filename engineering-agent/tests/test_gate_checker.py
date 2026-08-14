"""GateChecker 硬关卡校验器测试。

验收标准（spec.md Task 2）：单条 PASS/FAIL + 批量有 FAIL 整体 FAIL。
"""

from engineering_agent.loop.gate_checker import (
    CODING_EXIT_GATES,
    GateCheck,
    GateChecker,
)
from engineering_agent.manifest.store import ManifestStore


def test_single_pass(tmp_path):
    """单条校验 PASS。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": True})
    gate = GateCheck("compile", "phase3", "compile_passed", lambda v: v is True)
    result = GateChecker().check(gate, store)
    assert result.passed is True
    assert result.actual_value is True


def test_single_fail(tmp_path):
    """单条校验 FAIL。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": False})
    gate = GateCheck("compile", "phase3", "compile_passed", lambda v: v is True)
    result = GateChecker().check(gate, store)
    assert result.passed is False
    assert result.actual_value is False


def test_batch_all_pass(tmp_path):
    """批量全过 → all_pass=True。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": True, "lint_baseline_delta": 0})
    gates = [
        GateCheck("compile", "phase3", "compile_passed", lambda v: v is True),
        GateCheck("lint", "phase3", "lint_baseline_delta", lambda v: v == 0),
    ]
    result = GateChecker().check_all(gates, store)
    assert result.all_pass is True
    assert len(result.failures) == 0


def test_batch_has_failure(tmp_path):
    """批量有 FAIL → all_pass=False，failures 含未过项。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": True, "lint_baseline_delta": 3})
    gates = [
        GateCheck("compile", "phase3", "compile_passed", lambda v: v is True),
        GateCheck("lint", "phase3", "lint_baseline_delta", lambda v: v == 0),
    ]
    result = GateChecker().check_all(gates, store)
    assert result.all_pass is False
    assert len(result.failures) == 1
    assert result.failures[0].gate_id == "lint"


def test_coding_exit_gates_all_pass(tmp_path):
    """编码出口硬关卡清单全过。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {
        "task_status_all_done": True,
        "lint_baseline_delta": 0,
        "compile_passed": True,
        "test_regression_passed": True,
        "new_test_passed": True,
        "review_passed": True,
        "all_traces_exist": True,
    })
    result = GateChecker().check_all(CODING_EXIT_GATES, store)
    assert result.all_pass is True


def test_coding_exit_gates_has_failure(tmp_path):
    """编码出口硬关卡清单有 FAIL。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {
        "task_status_all_done": True,
        "lint_baseline_delta": 0,
        "compile_passed": False,
        "test_regression_passed": True,
        "new_test_passed": True,
        "review_passed": True,
        "all_traces_exist": True,
    })
    result = GateChecker().check_all(CODING_EXIT_GATES, store)
    assert result.all_pass is False
    assert len(result.failures) == 1
    assert result.failures[0].gate_id == "compile"


def test_field_missing(tmp_path):
    """字段不存在 → condition(None) → FAIL（None is True → False）。"""
    store = ManifestStore(tmp_path)
    gate = GateCheck("compile", "phase3", "compile_passed", lambda v: v is True)
    result = GateChecker().check(gate, store)
    assert result.passed is False
    assert result.actual_value is None


def test_empty_batch(tmp_path):
    """空 gate 列表 → all_pass=True（没有 FAIL）。"""
    store = ManifestStore(tmp_path)
    result = GateChecker().check_all([], store)
    assert result.all_pass is True
    assert len(result.results) == 0
