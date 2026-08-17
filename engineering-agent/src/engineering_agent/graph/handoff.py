"""结构化 handoff + 路由。

design doc §8.6/§9.4。
传递时机：第一轮并行纯净 → 汇聚后 Harness 提取 handoff 按 to 分发 → 下一轮补审。
handoff 是"提醒"不是"命令"，不触发硬拦截。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Handoff:
    """结构化 handoff（design doc §8.6）。

    from→to：reviewer 发现非自己维度的线索，传给对应 reviewer。
    status：pending→accepted/rejected。
    """

    from_reviewer: str
    to_reviewer: str
    file: str
    signal: str
    severity: str = "P2"
    line: int | None = None
    evidence: str = ""
    status: str = "pending"  # pending | accepted | rejected
    rejected_reason: str = ""


class HandoffRouter:
    """handoff 路由器。

    按 to_reviewer 分组 + 过滤 pending/accepted。
    """

    def route_by_target(
        self, handoffs: list[Handoff]
    ) -> dict[str, list[Handoff]]:
        """按 to_reviewer 分组路由。"""
        result: dict[str, list[Handoff]] = {}
        for h in handoffs:
            result.setdefault(h.to_reviewer, []).append(h)
        return result

    @staticmethod
    def filter_pending(handoffs: list[Handoff]) -> list[Handoff]:
        """过滤待处理的 handoff（status=pending）。"""
        return [h for h in handoffs if h.status == "pending"]

    @staticmethod
    def filter_accepted(handoffs: list[Handoff]) -> list[Handoff]:
        """过滤已采纳的 handoff。"""
        return [h for h in handoffs if h.status == "accepted"]
