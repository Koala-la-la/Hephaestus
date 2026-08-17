"""Handoff 测试。"""

from engineering_agent.graph.handoff import Handoff, HandoffRouter


def test_route_by_target():
    """按 to_reviewer 分组。"""
    handoffs = [
        Handoff(from_reviewer="performance", to_reviewer="robustness", file="a.go", signal="空指针"),
        Handoff(from_reviewer="standards", to_reviewer="robustness", file="b.go", signal="命名"),
        Handoff(from_reviewer="robustness", to_reviewer="performance", file="c.go", signal="热路径"),
    ]
    result = HandoffRouter().route_by_target(handoffs)
    assert len(result["robustness"]) == 2
    assert len(result["performance"]) == 1


def test_filter_pending():
    """过滤 pending。"""
    handoffs = [
        Handoff(from_reviewer="a", to_reviewer="b", file="a.go", signal="x", status="pending"),
        Handoff(from_reviewer="a", to_reviewer="b", file="b.go", signal="y", status="accepted"),
        Handoff(from_reviewer="a", to_reviewer="b", file="c.go", signal="z", status="pending"),
    ]
    pending = HandoffRouter.filter_pending(handoffs)
    assert len(pending) == 2
    assert all(h.status == "pending" for h in pending)


def test_filter_accepted():
    handoffs = [
        Handoff(from_reviewer="a", to_reviewer="b", file="a.go", signal="x", status="accepted"),
        Handoff(from_reviewer="a", to_reviewer="b", file="b.go", signal="y", status="pending"),
    ]
    accepted = HandoffRouter.filter_accepted(handoffs)
    assert len(accepted) == 1


def test_default_status():
    """默认 status=pending。"""
    h = Handoff(from_reviewer="a", to_reviewer="b", file="a.go", signal="x")
    assert h.status == "pending"


def test_empty():
    """空列表路由返回空。"""
    assert HandoffRouter().route_by_target([]) == {}
    assert HandoffRouter.filter_pending([]) == []
