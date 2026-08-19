"""ConfirmManager 测试。"""

import time

from engineering_agent.prompt.confirm import (
    ConfirmManager,
    ConfirmRequest,
    ConfirmType,
)


def test_request_and_get_pending():
    """提交请求 + 获取挂起。"""
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("c1", ConfirmType.PHASE_EXIT, "coding", "T-1 完成"))
    assert mgr.get_pending().request_id == "c1"


def test_resolve_approved():
    """解决——批准。"""
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("c1", ConfirmType.PHASE_EXIT, "coding", "T-1 完成"))
    result = mgr.resolve("c1", approved=True)
    assert result.approved is True
    assert mgr.get_pending() is None


def test_resolve_rejected():
    """解决——拒绝。"""
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("c1", ConfirmType.PHASE_EXIT, "coding", "T-1 完成"))
    result = mgr.resolve("c1", approved=False)
    assert result.approved is False


def test_priority_override_over_phase_exit():
    """覆盖确认优先于阶段出口。"""
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("p1", ConfirmType.PHASE_EXIT, "coding", "阶段出口"))
    mgr.request(ConfirmRequest("o1", ConfirmType.OVERRIDE, "coding", "覆盖 P0"))
    assert mgr.get_pending().request_id == "o1"


def test_priority_full_order():
    """优先级：override > phase_exit > grayscale。"""
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("g1", ConfirmType.GRAYSCALE, "release", "灰度 50%"))
    mgr.request(ConfirmRequest("p1", ConfirmType.PHASE_EXIT, "coding", "阶段出口"))
    mgr.request(ConfirmRequest("o1", ConfirmType.OVERRIDE, "coding", "覆盖 P0"))
    assert mgr.get_pending().request_id == "o1"
    mgr.resolve("o1", True)
    assert mgr.get_pending().request_id == "p1"
    mgr.resolve("p1", True)
    assert mgr.get_pending().request_id == "g1"


def test_timeout_default_reject():
    """超时默认拒绝（fail-safe）。"""
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest(
        "c1", ConfirmType.PHASE_EXIT, "coding", "T-1 完成",
        created_at=time.time() - 100000,
    ))
    timed_out = mgr.check_timeout()
    assert len(timed_out) == 1
    assert timed_out[0].approved is False
    assert timed_out[0].timed_out is True
    assert mgr.get_pending() is None


def test_no_timeout_not_rejected():
    """未超时不拒绝。"""
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("c1", ConfirmType.PHASE_EXIT, "coding", "T-1 完成"))
    assert len(mgr.check_timeout()) == 0
    assert mgr.get_pending() is not None
