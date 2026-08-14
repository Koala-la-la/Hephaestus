"""Loop 层集成验证测试。

验收标准（spec.md Task 5 + §4.5）：三块串联跑通。
"""

from engineering_agent.loop.gate_checker import CODING_EXIT_GATES, GateChecker
from engineering_agent.loop.state_tracker import LoopStateTracker
from engineering_agent.loop.upgrade_detector import UpgradeDetector
from engineering_agent.manifest.models import LoopType, SDLCPhase
from engineering_agent.manifest.store import ManifestStore


def test_case1_gate_fail(tmp_path):
    """case 1: manifest 写 FAIL 字段 → GateChecker FAIL。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": False})
    compile_gate = next(g for g in CODING_EXIT_GATES if g.gate_id == "compile")
    result = GateChecker().check(compile_gate, store)
    assert result.passed is False


def test_case2_gate_pass_after_fix(tmp_path):
    """case 2: 修正为 PASS → GateChecker PASS。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": False})
    store.update_field("phase3", "compile_passed", True)
    compile_gate = next(g for g in CODING_EXIT_GATES if g.gate_id == "compile")
    result = GateChecker().check(compile_gate, store)
    assert result.passed is True


def test_case3_batch_fail_then_pass(tmp_path):
    """case 3: 批量校验有 FAIL → 整体 FAIL，修正后全过 PASS。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {
        "task_status_all_done": True, "lint_baseline_delta": 0,
        "compile_passed": False, "test_regression_passed": True,
        "new_test_passed": True, "review_passed": True,
        "all_traces_exist": True,
    })
    checker = GateChecker()
    assert checker.check_all(CODING_EXIT_GATES, store).all_pass is False

    store.update_field("phase3", "compile_passed", True)
    assert checker.check_all(CODING_EXIT_GATES, store).all_pass is True


def test_case4_state_tracker(tmp_path):
    """case 4: LoopStateTracker 更新定位层 → 读回一致 + 清空 pending_findings。"""
    store = ManifestStore(tmp_path)
    tracker = LoopStateTracker(store)
    tracker.init_state(SDLCPhase.CODING, "T-1")
    tracker.update_location(loop_type=LoopType.A)
    tracker.update_snapshot(review_round=2, pending_findings=["P0-001"])

    state = tracker.get_state()
    assert state.location.current_task_id == "T-1"
    assert state.location.current_loop_type == LoopType.A
    assert state.snapshot.review_round == 2

    tracker.clear_pending_findings()
    assert tracker.get_state().snapshot.pending_findings == []


def test_case5_upgrade_ratio(tmp_path):
    """case 5: needs_revalidation 占比 80% → 升级。"""
    detector = UpgradeDetector(ratio_threshold=0.6)
    decision = detector.detect(
        needs_revalidation=list("abcde"),
        reviewed=["a"],
        finding_refs={},
        consecutive_failures=0,
    )
    assert decision.should_upgrade is True


def test_case6_no_upgrade_when_stable(tmp_path):
    """case 6: 三条都不满足 → 不升级。"""
    detector = UpgradeDetector()
    decision = detector.detect(
        needs_revalidation=list("abcde"),
        reviewed=list("abcd"),  # 20%
        finding_refs={"F-1": ["4.2"]},  # 非需求章
        consecutive_failures=1,
    )
    assert decision.should_upgrade is False


def test_case7_full_workflow(tmp_path):
    """case 7: 完整工作流——FAIL→修正→PASS→state更新→不升级。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {
        "task_status_all_done": True, "lint_baseline_delta": 0,
        "compile_passed": False, "test_regression_passed": True,
        "new_test_passed": True, "review_passed": False,
        "all_traces_exist": True,
    })

    tracker = LoopStateTracker(store)
    tracker.init_state(SDLCPhase.CODING, "T-1")
    tracker.update_snapshot(review_round=1, pending_findings=["F-1"])

    checker = GateChecker()
    result = checker.check_all(CODING_EXIT_GATES, store)
    assert result.all_pass is False
    assert len(result.failures) == 2

    store.update_field("phase3", "compile_passed", True)
    store.update_field("phase3", "review_passed", True)
    assert checker.check_all(CODING_EXIT_GATES, store).all_pass is True

    tracker.clear_pending_findings()
    assert tracker.get_state().snapshot.pending_findings == []

    detector = UpgradeDetector()
    decision = detector.detect(
        needs_revalidation=["auth/login.go"],
        reviewed=["auth/login.go"],
        finding_refs={},
        consecutive_failures=0,
    )
    assert decision.should_upgrade is False
