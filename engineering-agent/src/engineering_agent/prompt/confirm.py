"""confirm token 机制。

design doc §11.3 + §A4。
两类确认：阶段出口 + 覆盖。
串行优先级：覆盖 > 阶段出口 > 灰度。
超时默认拒绝（阶段出口→不推进；覆盖→不覆盖 P0 仍拦）。

串行依赖链（不是平行冲突）：
覆盖确认 → 解决 → task 真正完成 → 阶段出口确认。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class ConfirmType(str, Enum):
    """确认类型。"""

    PHASE_EXIT = "phase_exit"
    OVERRIDE = "override"
    GRAYSCALE = "grayscale"


# 优先级（值越小越高）
_PRIORITY_ORDER: dict[ConfirmType, int] = {
    ConfirmType.OVERRIDE: 0,
    ConfirmType.PHASE_EXIT: 1,
    ConfirmType.GRAYSCALE: 2,
}


@dataclass
class ConfirmRequest:
    """确认请求。

    summary 由 Harness 从 manifest 生成，不让 agent 自己写（防美化）。
    """

    request_id: str
    confirm_type: ConfirmType
    phase: str
    summary: str
    confirm_consequence: str = ""
    reject_consequence: str = ""
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 86400.0  # 24 小时


@dataclass
class ConfirmResult:
    """确认结果。"""

    request_id: str
    approved: bool
    timed_out: bool = False


class ConfirmManager:
    """确认请求管理器。

    串行单挂起队列——同一时间最多 1 个 confirm 挂起。
    优先级：override > phase_exit > grayscale。
    超时默认拒绝（fail-safe）。
    """

    def __init__(self) -> None:
        self._queue: list[ConfirmRequest] = []
        self._resolved: dict[str, ConfirmResult] = {}

    def request(self, req: ConfirmRequest) -> ConfirmRequest | None:
        """提交确认请求。按优先级排序后返回当前挂起的。"""
        self._queue.append(req)
        self._queue.sort(key=lambda r: _PRIORITY_ORDER.get(r.confirm_type, 99))
        return self._queue[0] if self._queue else None

    def get_pending(self) -> ConfirmRequest | None:
        """获取当前挂起的请求（优先级最高）。"""
        return self._queue[0] if self._queue else None

    def resolve(self, request_id: str, approved: bool) -> ConfirmResult:
        """解决确认请求。从队列移除，记录结果。"""
        self._queue = [
            r for r in self._queue if r.request_id != request_id
        ]
        result = ConfirmResult(request_id=request_id, approved=approved)
        self._resolved[request_id] = result
        return result

    def check_timeout(self, now: float | None = None) -> list[ConfirmResult]:
        """检查超时，返回超时结果。超时默认拒绝（fail-safe）。"""
        if now is None:
            now = time.time()
        timed_out: list[ConfirmResult] = []
        for req in self._queue[:]:
            if now - req.created_at > req.timeout_seconds:
                self._queue.remove(req)
                result = ConfirmResult(
                    request_id=req.request_id,
                    approved=False,
                    timed_out=True,
                )
                self._resolved[req.request_id] = result
                timed_out.append(result)
        return timed_out

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    def get_result(self, request_id: str) -> ConfirmResult | None:
        """获取已解决的结果。"""
        return self._resolved.get(request_id)
