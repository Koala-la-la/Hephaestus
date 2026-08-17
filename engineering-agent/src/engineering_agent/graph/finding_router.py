"""finding 三级分级拦截路由器。

design doc §9.2。
机器 P0 → Harness 硬拦，不可覆盖
agent P0 → Harness 拦，人可显式覆盖（留痕）
P1/P2 → 记录不阻断
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engineering_agent.manifest.models import (
    FindingSeverity,
    FindingSource,
    ReviewFinding,
)


@dataclass
class FindingAction:
    """单条 finding 的处置方式。"""

    action: str  # "block" | "block_overridable" | "record"
    overridable: bool
    reason: str


@dataclass
class BatchFindingAction:
    """批量 finding 路由结果。"""

    actions: list[FindingAction] = field(default_factory=list)

    @property
    def has_block(self) -> bool:
        """是否有阻断项（block 或 block_overridable）。"""
        return any(
            a.action in ("block", "block_overridable") for a in self.actions
        )

    @property
    def blocks(self) -> list[FindingAction]:
        """阻断项。"""
        return [
            a for a in self.actions if a.action in ("block", "block_overridable")
        ]


class FindingRouter:
    """三级分级拦截路由器（design doc §9.2）。

    按 finding 的 source + severity 决定处置方式。
    """

    def route(self, finding: ReviewFinding) -> FindingAction:
        """单条路由。"""
        if (
            finding.source == FindingSource.MACHINE
            and finding.severity == FindingSeverity.P0
        ):
            return FindingAction(
                "block", overridable=False, reason="机器 P0 硬拦不可覆盖"
            )
        if (
            finding.source == FindingSource.AGENT
            and finding.severity == FindingSeverity.P0
        ):
            return FindingAction(
                "block_overridable", overridable=True, reason="agent P0 半硬人可覆盖"
            )
        return FindingAction(
            "record", overridable=False, reason="P1/P2 记录不阻断"
        )

    def route_batch(
        self, findings: list[ReviewFinding]
    ) -> BatchFindingAction:
        """批量路由。"""
        return BatchFindingAction(
            actions=[self.route(f) for f in findings]
        )
