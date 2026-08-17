"""Graph 层集成验证测试。"""

from engineering_agent.graph.context_router import ReviewerContextRouter
from engineering_agent.graph.finding_router import FindingRouter
from engineering_agent.graph.goal_checker import CriticGoalChecker
from engineering_agent.graph.handoff import Handoff, HandoffRouter
from engineering_agent.manifest.models import (
    FindingSeverity,
    FindingSource,
    ReviewFinding,
)


def test_case1_finding_router():
    """case 1: 三级分级拦截。"""
    r = FindingRouter()
    assert r.route(ReviewFinding(
        severity=FindingSeverity.P0, source=FindingSource.MACHINE, file="a.go"
    )).action == "block"
    assert r.route(ReviewFinding(
        severity=FindingSeverity.P0, source=FindingSource.AGENT, file="b.go"
    )).action == "block_overridable"
    assert r.route(ReviewFinding(
        severity=FindingSeverity.P1, source=FindingSource.AGENT, file="c.go"
    )).action == "record"


def test_case2_context_router():
    """case 2: 共享层 + 维度子集。"""
    r = ReviewerContextRouter()
    assert "spec_sections" in r.get_shared_layer()
    assert "hot_path_code" in r.get_dimension_subset("performance")


def test_case3_handoff():
    """case 3: handoff 分组路由。"""
    r = HandoffRouter()
    handoffs = [
        Handoff(from_reviewer="performance", to_reviewer="robustness", file="a.go", signal="空指针"),
        Handoff(from_reviewer="standards", to_reviewer="performance", file="b.go", signal="命名"),
    ]
    grouped = r.route_by_target(handoffs)
    assert len(grouped["robustness"]) == 1
    assert len(grouped["performance"]) == 1
    assert len(HandoffRouter.filter_pending(handoffs)) == 2


def test_case4_goal_checker():
    """case 4: 目标可衡量性粗筛。"""
    c = CriticGoalChecker()
    assert c.machine_check("P99 < 200ms") is True
    assert c.machine_check("性能要好") is False


def test_case5_full_workflow():
    """case 5: 完整工作流——四块串联。"""
    # 1. finding 路由
    batch = FindingRouter().route_batch([
        ReviewFinding(severity=FindingSeverity.P0, source=FindingSource.MACHINE, file="a.go"),
        ReviewFinding(severity=FindingSeverity.P1, source=FindingSource.AGENT, file="b.go"),
    ])
    assert batch.has_block is True

    # 2. context 路由
    all_ctx = ReviewerContextRouter().get_all_for_reviewer("robustness")
    assert "spec_sections" in all_ctx
    assert "error_handling" in all_ctx

    # 3. handoff
    grouped = HandoffRouter().route_by_target([
        Handoff(from_reviewer="performance", to_reviewer="robustness", file="a.go", signal="空指针"),
    ])
    assert "robustness" in grouped

    # 4. goal 检查
    assert CriticGoalChecker().machine_check("P99 < 200ms") is True
