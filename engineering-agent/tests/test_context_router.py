"""ReviewerContextRouter 测试。"""

from engineering_agent.graph.context_router import ReviewerContextRouter


def test_shared_layer():
    r = ReviewerContextRouter()
    shared = r.get_shared_layer()
    assert "spec_sections" in shared
    assert "tasks_current" in shared
    assert "diff" in shared
    assert "applicable_norms" in shared


def test_dimension_subset_performance():
    assert "hot_path_code" in ReviewerContextRouter().get_dimension_subset("performance")
    assert "performance_norms" in ReviewerContextRouter().get_dimension_subset("performance")


def test_dimension_subset_robustness():
    dims = ReviewerContextRouter().get_dimension_subset("robustness")
    assert "error_handling" in dims
    assert "resource_norms" in dims


def test_dimension_subset_unknown():
    """未知 reviewer 返回空列表。"""
    assert ReviewerContextRouter().get_dimension_subset("unknown") == []


def test_all_for_reviewer():
    """完整上下文 = 共享层 + 维度子集。"""
    all_ctx = ReviewerContextRouter().get_all_for_reviewer("standards")
    assert "spec_sections" in all_ctx  # 共享层
    assert "naming_rules" in all_ctx  # 维度子集


def test_all_reviewers():
    """5 个 reviewer 角色。"""
    reviewers = ReviewerContextRouter.get_all_reviewers()
    assert len(reviewers) == 5
    assert "performance" in reviewers
    assert "contract-trust" in reviewers
