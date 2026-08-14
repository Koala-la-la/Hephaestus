"""LoopStateTracker 测试。

验收标准：更新定位层+快照层 → 读回一致 + pending_findings 清空。
"""

from engineering_agent.loop.state_tracker import LoopStateTracker
from engineering_agent.manifest.models import LoopType, SDLCPhase
from engineering_agent.manifest.store import ManifestStore


def test_init_state(tmp_path):
    """初始化 loop_state → 读回一致。"""
    store = ManifestStore(tmp_path)
    tracker = LoopStateTracker(store)
    state = tracker.init_state(SDLCPhase.CODING, "T-1")
    assert state.location.current_phase == SDLCPhase.CODING
    assert state.location.current_task_id == "T-1"

    state2 = tracker.get_state()
    assert state2 is not None
    assert state2.location.current_task_id == "T-1"


def test_get_state_none(tmp_path):
    """未初始化时返回 None。"""
    store = ManifestStore(tmp_path)
    tracker = LoopStateTracker(store)
    assert tracker.get_state() is None


def test_update_location(tmp_path):
    """更新定位层——只更新非 None 字段。"""
    store = ManifestStore(tmp_path)
    tracker = LoopStateTracker(store)
    tracker.init_state(SDLCPhase.CODING, "T-1")
    tracker.update_location(loop_type=LoopType.B, task_id="T-2")
    state = tracker.get_state()
    assert state.location.current_loop_type == LoopType.B
    assert state.location.current_task_id == "T-2"
    # 未更新的字段保持
    assert state.location.current_phase == SDLCPhase.CODING


def test_update_snapshot(tmp_path):
    """更新进度快照层。"""
    store = ManifestStore(tmp_path)
    tracker = LoopStateTracker(store)
    tracker.init_state(SDLCPhase.CODING)
    tracker.update_snapshot(
        files_modified=["auth/login.go"],
        review_round=2,
        pending_findings=["P0-001"],
    )
    state = tracker.get_state()
    assert state.snapshot.files_modified == ["auth/login.go"]
    assert state.snapshot.review_round == 2
    assert state.snapshot.pending_findings == ["P0-001"]


def test_clear_pending_findings(tmp_path):
    """review PASS 后清空 pending_findings（§8.4 边界）。"""
    store = ManifestStore(tmp_path)
    tracker = LoopStateTracker(store)
    tracker.init_state(SDLCPhase.CODING)
    tracker.update_snapshot(pending_findings=["P0-001", "P1-002"])
    assert tracker.get_state().snapshot.pending_findings == ["P0-001", "P1-002"]

    tracker.clear_pending_findings()
    assert tracker.get_state().snapshot.pending_findings == []


def test_update_location_none_state(tmp_path):
    """未初始化时 update_location 返回 None。"""
    store = ManifestStore(tmp_path)
    tracker = LoopStateTracker(store)
    result = tracker.update_location(phase=SDLCPhase.CODING)
    assert result is None


def test_roundtrip_persistence(tmp_path):
    """更新后读回一致（持久化到 manifest JSON）。"""
    store = ManifestStore(tmp_path)
    tracker = LoopStateTracker(store)
    tracker.init_state(SDLCPhase.TESTING, "T-3")
    tracker.update_location(loop_type=LoopType.GRAPH)
    tracker.update_snapshot(completed_steps=["step1", "step2"])

    state = tracker.get_state()
    assert state.location.current_phase == SDLCPhase.TESTING
    assert state.location.current_task_id == "T-3"
    assert state.location.current_loop_type == LoopType.GRAPH
    assert state.snapshot.completed_steps == ["step1", "step2"]
