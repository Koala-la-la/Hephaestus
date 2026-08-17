"""FailurePatternStore 测试。"""

from engineering_agent.context.failure_patterns import (
    FailurePattern,
    FailurePatternStore,
)


def test_add_and_count():
    store = FailurePatternStore()
    store.add(FailurePattern("auth", "null_pointer", "P0", "coding"))
    store.add(FailurePattern("payment", "timeout", "P1", "testing"))
    assert store.count() == 2


def test_search_by_module():
    store = FailurePatternStore()
    store.add(FailurePattern("auth", "null_pointer", "P0", "coding"))
    store.add(FailurePattern("payment", "timeout", "P1", "testing"))
    store.add(FailurePattern("auth", "timeout", "P1", "coding"))
    results = store.search(module="auth")
    assert len(results) == 2
    assert all(p.module == "auth" for p in results)


def test_search_by_error_type():
    store = FailurePatternStore()
    store.add(FailurePattern("auth", "null_pointer", "P0", "coding"))
    store.add(FailurePattern("payment", "timeout", "P1", "testing"))
    store.add(FailurePattern("auth", "timeout", "P1", "coding"))
    results = store.search(error_type="timeout")
    assert len(results) == 2
    assert all(p.error_type == "timeout" for p in results)


def test_search_multiple_tags():
    """多标签组合（AND 关系）。"""
    store = FailurePatternStore()
    store.add(FailurePattern("auth", "timeout", "P1", "coding"))
    store.add(FailurePattern("auth", "timeout", "P0", "testing"))
    store.add(FailurePattern("payment", "timeout", "P1", "coding"))
    results = store.search(module="auth", error_type="timeout", phase="coding")
    assert len(results) == 1
    assert results[0].severity == "P1"


def test_search_empty():
    store = FailurePatternStore()
    store.add(FailurePattern("auth", "null_pointer", "P0", "coding"))
    assert store.search(module="nonexistent") == []


def test_search_all_none_returns_all():
    store = FailurePatternStore()
    store.add(FailurePattern("auth", "null_pointer", "P0", "coding"))
    store.add(FailurePattern("payment", "timeout", "P1", "testing"))
    assert len(store.search()) == 2


def test_search_by_severity():
    store = FailurePatternStore()
    store.add(FailurePattern("auth", "null_pointer", "P0", "coding"))
    store.add(FailurePattern("payment", "timeout", "P1", "testing"))
    results = store.search(severity="P0")
    assert len(results) == 1
    assert results[0].module == "auth"


def test_content_fields():
    """自然语言内容字段可读写。"""
    store = FailurePatternStore()
    store.add(FailurePattern(
        "auth", "null_pointer", "P0", "coding",
        symptom="空指针崩溃", root_cause="缺检查", fix="加 early return",
    ))
    results = store.search(module="auth")
    assert results[0].symptom == "空指针崩溃"
    assert results[0].root_cause == "缺检查"
    assert results[0].fix == "加 early return"
