"""manifest 六片模型序列化/反序列化往返测试。

验收标准（spec.md Task 2）：六片模型的 model_dump_json() / model_validate_json() 往返一致。
"""

import json

import pytest

from engineering_agent.manifest.models import (
    ChangeType,
    CommonManifest,
    FindingSeverity,
    FindingSource,
    GrayscaleStatus,
    LoopState,
    LoopStateLocation,
    LoopStateSnapshot,
    LoopType,
    Phase1Manifest,
    Phase2Manifest,
    Phase3Manifest,
    Phase4Manifest,
    Phase5Manifest,
    ReviewFinding,
    SDLCPhase,
    TaskSpec,
    TaskStatus,
    ThresholdSpec,
)


# ──────────────────────────────────────────────
# common 片
# ──────────────────────────────────────────────


def test_common_roundtrip():
    """common 片序列化/反序列化往返一致。"""
    m = CommonManifest(
        spec_sha="abc123def456",
        spec_version="v3",
        change_type=ChangeType.MINOR,
    )
    j = m.model_dump_json()
    m2 = CommonManifest.model_validate_json(j)
    assert m == m2
    assert m2.spec_sha == "abc123def456"
    assert m2.change_type == ChangeType.MINOR


def test_common_change_type_none():
    """change_type 可为 None（spec 未变更时）。"""
    m = CommonManifest(spec_sha="abc", spec_version="v3")
    j = m.model_dump_json()
    m2 = CommonManifest.model_validate_json(j)
    assert m2.change_type is None


# ──────────────────────────────────────────────
# phase1 片
# ──────────────────────────────────────────────


def test_phase1_roundtrip():
    """phase1 片序列化/反序列化往返一致。"""
    m = Phase1Manifest(
        sections_status={"1": "filled", "2": "filled", "3": "filled"},
        goal_measurable=True,
        goal_measurable_evidence="P99 < 200ms in 1000 QPS",
        nonfunctional_checked=True,
    )
    j = m.model_dump_json()
    m2 = Phase1Manifest.model_validate_json(j)
    assert m == m2
    assert m2.goal_measurable is True


# ──────────────────────────────────────────────
# phase2 片
# ──────────────────────────────────────────────


def test_phase2_roundtrip():
    """phase2 片序列化/反序列化往返一致。"""
    m = Phase2Manifest(
        sections_status={"4": "filled", "5": "na"},
        tradeoff_count=2,
        monitoring_thresholds={
            "p99": ThresholdSpec(metric="p99", op="<", value=200, unit="ms"),
        },
        rollback_plan_exists=True,
        tasks=[
            TaskSpec(
                id="T-1",
                spec_refs=["4.2", "5.1"],
                estimated_files=["auth/*"],
                estimated_loc=30,
                status=TaskStatus.PENDING,
                depends_on=[],
            ),
        ],
        reverse_coverage={"4.2": ["T-1"], "5.1": ["T-1"]},
    )
    j = m.model_dump_json()
    m2 = Phase2Manifest.model_validate_json(j)
    assert m == m2
    assert m2.tasks[0].spec_refs == ["4.2", "5.1"]
    assert m2.monitoring_thresholds["p99"].op == "<"


# ──────────────────────────────────────────────
# phase3 片
# ──────────────────────────────────────────────


def test_phase3_roundtrip():
    """phase3 片序列化/反序列化往返一致。"""
    m = Phase3Manifest(
        task_status_all_done=False,
        lint_baseline_delta=0,
        compile_passed=True,
        test_regression_passed=True,
        new_test_passed=True,
        review_passed=False,
        review_findings=[
            ReviewFinding(
                severity=FindingSeverity.P0,
                source=FindingSource.MACHINE,
                file="auth/login.go",
                line=42,
                fixed=False,
            ),
            ReviewFinding(
                severity=FindingSeverity.P1,
                source=FindingSource.AGENT,
                file="auth/session.go",
                fixed=False,
            ),
        ],
        needs_revalidation=["auth/login.go", "session/manager.go"],
        needs_revalidation_reviewed=["auth/login.go"],
        to_create=["auth/newmod.go"],
        created=[],
        all_traces_exist=True,
        loop_state=LoopState(
            location=LoopStateLocation(
                current_phase=SDLCPhase.CODING,
                current_task_id="T-1",
                current_loop_type=LoopType.A,
            ),
            snapshot=LoopStateSnapshot(
                files_modified=["auth/login.go"],
                completed_steps=["step1_read_spec"],
                review_round=2,
                pending_findings=["P0-001"],
                revalidation_checked=["auth/login.go"],
            ),
        ),
    )
    j = m.model_dump_json()
    m2 = Phase3Manifest.model_validate_json(j)
    assert m == m2
    assert m2.review_findings[0].source == FindingSource.MACHINE
    assert m2.loop_state.location.current_phase == SDLCPhase.CODING
    assert m2.loop_state.snapshot.review_round == 2


# ──────────────────────────────────────────────
# phase4 片
# ──────────────────────────────────────────────


def test_phase4_roundtrip():
    """phase4 片序列化/反序列化往返一致。"""
    m = Phase4Manifest(
        all_tests_passed=True,
        line_coverage=82.5,
        branch_coverage=71.2,
        coverage_met=True,
        three_category_coverage={
            "happy_path": True,
            "boundary": True,
            "exception": True,
        },
        test_report_structured=True,
    )
    j = m.model_dump_json()
    m2 = Phase4Manifest.model_validate_json(j)
    assert m == m2
    assert m2.coverage_met is True
    assert m2.three_category_coverage["boundary"] is True


# ──────────────────────────────────────────────
# phase5 片
# ──────────────────────────────────────────────


def test_phase5_roundtrip():
    """phase5 片序列化/反序列化往返一致。"""
    m = Phase5Manifest(
        release_package_sha="sha-abc",
        rollback_plan="kubectl rollout undo deployment/auth",
        grayscale_strategy=[5, 25, 50, 100],
        monitoring_thresholds={
            "error_rate": ThresholdSpec(metric="error_rate", op="<", value=0.1, unit="%"),
        },
        grayscale_current=25,
        grayscale_phase="waiting_confirm",
        grayscale_status=GrayscaleStatus.IN_PROGRESS,
    )
    j = m.model_dump_json()
    m2 = Phase5Manifest.model_validate_json(j)
    assert m == m2
    assert m2.grayscale_current == 25
    assert m2.monitoring_thresholds["error_rate"].value == 0.1


# ──────────────────────────────────────────────
# 默认值
# ──────────────────────────────────────────────


def test_default_values():
    """六片模型的默认值正确。"""
    p3 = Phase3Manifest()
    assert p3.lint_baseline_delta == 0
    assert p3.needs_revalidation == []
    assert p3.loop_state is None

    p4 = Phase4Manifest()
    assert p4.three_category_coverage == {
        "happy_path": False,
        "boundary": False,
        "exception": False,
    }

    p5 = Phase5Manifest()
    assert p5.grayscale_strategy == [5, 25, 50, 100]
    assert p5.grayscale_status == GrayscaleStatus.IN_PROGRESS


# ──────────────────────────────────────────────
# 枚举可序列化
# ──────────────────────────────────────────────


def test_enums_are_str_enum():
    """所有枚举继承 str，JSON 序列化为字符串值而非 {name,value}。"""
    j = json.dumps({"change_type": ChangeType.MAJOR})
    assert "major" in j

    j = json.dumps({"source": FindingSource.MACHINE})
    assert "machine" in j

    j = json.dumps({"loop_type": LoopType.GRAPH})
    assert "Graph" in j
