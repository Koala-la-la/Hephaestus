"""ContextMatrix 测试。"""

from engineering_agent.context.matrix import ContextMatrix


def test_identity_push_all_phases():
    """identity 全阶段 Push。"""
    m = ContextMatrix()
    for p in ("requirement", "design", "coding", "testing", "release"):
        assert m.get_mode(p, "identity") == "push"


def test_task_spec_push_all_phases():
    """task_spec 全阶段 Push。"""
    m = ContextMatrix()
    for p in ("requirement", "design", "coding", "testing", "release"):
        assert m.get_mode(p, "task_spec") == "push"


def test_code_pull_all_phases():
    """code 全阶段 Pull。"""
    m = ContextMatrix()
    for p in ("requirement", "design", "coding", "testing", "release"):
        assert m.get_mode(p, "code") == "pull"


def test_norms_push_requirement_and_coding():
    """norms 在需求+编码 Push，其他 Pull。"""
    m = ContextMatrix()
    assert m.get_mode("requirement", "norms") == "push"
    assert m.get_mode("coding", "norms") == "push"
    assert m.get_mode("design", "norms") == "pull"
    assert m.get_mode("testing", "norms") == "pull"


def test_feedback_push_all():
    """feedback 全阶段 Push。"""
    m = ContextMatrix()
    for p in ("requirement", "design", "coding", "testing", "release"):
        assert m.get_mode(p, "feedback") == "push"


def test_baseline_push_coding_testing_release():
    """baseline 编码/测试/上线 Push，需求/设计 Pull。"""
    m = ContextMatrix()
    assert m.get_mode("coding", "baseline") == "push"
    assert m.get_mode("testing", "baseline") == "push"
    assert m.get_mode("release", "baseline") == "push"
    assert m.get_mode("requirement", "baseline") == "pull"
    assert m.get_mode("design", "baseline") == "pull"


def test_get_push_types_coding():
    """编码阶段 Push 类型列表。"""
    m = ContextMatrix()
    push = m.get_push_types("coding")
    assert "identity" in push
    assert "task_spec" in push
    assert "feedback" in push
    assert "baseline" in push
    assert "norms" in push
    assert "code" not in push
    assert "history" not in push
