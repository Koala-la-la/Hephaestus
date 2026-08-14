"""loop_state 管理器。

design doc §8.4。loop_state 两层（定位层+进度快照层），存 manifest phase3.loop_state。
边界：只存进度不存结果——结果在 manifest 的 status 字段（如 review_passed）。
review PASS 后 pending_findings 必须清空。
"""

from __future__ import annotations

from engineering_agent.manifest.models import (
    LoopState,
    LoopStateLocation,
    LoopStateSnapshot,
    LoopType,
    SDLCPhase,
)
from engineering_agent.manifest.store import ManifestStore


class LoopStateTracker:
    """loop_state 管理器。

    定位层（location）：Harness 调用，每次状态切换时更新
    进度快照层（snapshot）：机器可验证字段从客观源拉取
    存 manifest phase3.loop_state 字段（复用 Harness 层 ManifestStore）
    """

    def __init__(self, store: ManifestStore) -> None:
        self._store = store

    def get_state(self) -> LoopState | None:
        """读取当前 loop_state。不存在返回 None。"""
        data = self._store.get_field("phase3", "loop_state")
        if data is None:
            return None
        return LoopState.model_validate(data)

    def init_state(
        self, phase: SDLCPhase, task_id: str | None = None
    ) -> LoopState:
        """初始化 loop_state（如果不存在）。"""
        state = LoopState(
            location=LoopStateLocation(
                current_phase=phase,
                current_task_id=task_id,
            ),
            snapshot=LoopStateSnapshot(),
        )
        self._save(state)
        return state

    def update_location(
        self,
        phase: SDLCPhase | None = None,
        task_id: str | None = None,
        subtask: str | None = None,
        loop_type: LoopType | None = None,
    ) -> LoopState | None:
        """更新定位层。只更新非 None 的字段。"""
        state = self.get_state()
        if state is None:
            return None
        if phase is not None:
            state.location.current_phase = phase
        if task_id is not None:
            state.location.current_task_id = task_id
        if subtask is not None:
            state.location.current_subtask = subtask
        if loop_type is not None:
            state.location.current_loop_type = loop_type
        self._save(state)
        return state

    def update_snapshot(
        self,
        files_modified: list[str] | None = None,
        completed_steps: list[str] | None = None,
        review_round: int | None = None,
        pending_findings: list[str] | None = None,
        revalidation_checked: list[str] | None = None,
    ) -> LoopState | None:
        """更新进度快照层。只更新非 None 的字段。"""
        state = self.get_state()
        if state is None:
            return None
        if files_modified is not None:
            state.snapshot.files_modified = files_modified
        if completed_steps is not None:
            state.snapshot.completed_steps = completed_steps
        if review_round is not None:
            state.snapshot.review_round = review_round
        if pending_findings is not None:
            state.snapshot.pending_findings = pending_findings
        if revalidation_checked is not None:
            state.snapshot.revalidation_checked = revalidation_checked
        self._save(state)
        return state

    def clear_pending_findings(self) -> None:
        """review PASS 后清空 pending_findings（§8.4 边界）。

        判定转到 manifest.status——loop_state 只存进度不存结果。
        """
        state = self.get_state()
        if state is None:
            return
        state.snapshot.pending_findings = []
        self._save(state)

    def _save(self, state: LoopState) -> None:
        """存 manifest phase3.loop_state（model_dump mode=json 确保枚举序列化）。"""
        self._store.update_field(
            "phase3", "loop_state", state.model_dump(mode="json")
        )
