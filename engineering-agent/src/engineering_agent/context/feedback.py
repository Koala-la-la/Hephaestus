"""反馈保鲜器。

design doc §10.3。反馈类只留最新——set 覆盖旧值，不累积。
防止旧反馈占用上下文窗口、稀释信噪比（Lost in the Middle）。
"""

from __future__ import annotations

from typing import Any


class FeedbackKeeper:
    """反馈保鲜器。

    in-memory dict——反馈是临时的（只留最新，不需要持久化到 manifest）。
    set 覆盖旧值不累积——"只留最新"的核心行为（§10.3）。
    """

    def __init__(self) -> None:
        self._feedbacks: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """设置最新反馈（覆盖旧值，不累积）。"""
        self._feedbacks[key] = value

    def get(self, key: str) -> Any:
        """读取最新反馈。不存在返回 None。"""
        return self._feedbacks.get(key)

    def clear(self, key: str) -> None:
        """清除某类反馈。"""
        self._feedbacks.pop(key, None)

    def clear_all(self) -> None:
        """清除所有反馈。"""
        self._feedbacks.clear()

    def keys(self) -> list[str]:
        """所有反馈键。"""
        return list(self._feedbacks.keys())
