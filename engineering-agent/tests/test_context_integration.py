"""Context 层集成验证测试。"""

from engineering_agent.context.failure_patterns import (
    FailurePattern,
    FailurePatternStore,
)
from engineering_agent.context.feedback import FeedbackKeeper
from engineering_agent.context.matrix import ContextMatrix


def test_case1_matrix_query():
    """case 1: ContextMatrix 查询 Push/Pull。"""
    m = ContextMatrix()
    assert m.get_mode("coding", "task_spec") == "push"
    assert m.get_mode("coding", "code") == "pull"
    assert m.get_mode("requirement", "norms") == "push"


def test_case2_feedback_overwrite():
    """case 2: FeedbackKeeper set 覆盖不累积。"""
    keeper = FeedbackKeeper()
    keeper.set("lint", "5 warnings")
    keeper.set("lint", "0 warnings")
    assert keeper.get("lint") == "0 warnings"
    keeper.clear("lint")
    assert keeper.get("lint") is None


def test_case3_pattern_search():
    """case 3: FailurePatternStore 按标签检索。"""
    store = FailurePatternStore()
    store.add(FailurePattern("auth", "null_pointer", "P0", "coding"))
    store.add(FailurePattern("auth", "timeout", "P1", "testing"))
    store.add(FailurePattern("payment", "timeout", "P0", "coding"))
    results = store.search(module="auth", phase="coding")
    assert len(results) == 1
    assert results[0].error_type == "null_pointer"
    results = store.search(error_type="timeout")
    assert len(results) == 2


def test_case4_full_workflow():
    """case 4: 完整工作流——matrix + feedback + pattern。"""
    m = ContextMatrix()
    keeper = FeedbackKeeper()
    store = FailurePatternStore()

    push_types = m.get_push_types("coding")
    assert "identity" in push_types
    assert "code" not in push_types

    keeper.set("lint", "pass")
    keeper.set("lint", "0 warnings")
    assert keeper.get("lint") == "0 warnings"

    store.add(FailurePattern(
        "auth", "null_pointer", "P0", "coding",
        symptom="validateToken 前未检查 user==nil",
        root_cause="缺少空值检查",
        fix="加 early return if user is None",
    ))
    results = store.search(module="auth", phase="coding")
    assert len(results) == 1
    assert "nil" in results[0].symptom
