"""minor→major 升级判定。

design doc §7.3。三个触发条件：
1. needs_revalidation 占比 > 阈值（默认 60%）——改动波及面太大
2. finding 涉及需求章(1-3)或方案概览(4.1)——minor 不该动这些章节
3. 连续 N 轮同类失败（默认 2 轮）——不是单点错，是设计层面问题
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 需求章(1-3) + 方案概览(4.1)——minor 不该动这些章节
_MAJOR_SPEC_PREFIXES = ("1.", "2.", "3.")


@dataclass
class UpgradeDecision:
    """升级判定结果。

    should_upgrade=True → 触发 minor→major 升级
    reasons 记录哪些条件触发了（可多条同时满足）
    """

    should_upgrade: bool = False
    reasons: list[str] = field(default_factory=list)


class UpgradeDetector:
    """minor→major 升级判定器。

    三个触发条件各自判定 + 综合判定（任一满足即升级）。
    """

    def __init__(
        self,
        ratio_threshold: float = 0.6,
        consecutive_failures: int = 2,
    ) -> None:
        self._ratio_threshold = ratio_threshold
        self._consecutive_failures = consecutive_failures

    def check_ratio(
        self,
        needs_revalidation: list[str],
        reviewed: list[str],
    ) -> bool:
        """检查 needs_revalidation 未审占比是否超阈值。

        占比 = 未审数 / 总数。超阈值 → 升级。
        """
        if not needs_revalidation:
            return False
        unreviewed = set(needs_revalidation) - set(reviewed)
        ratio = len(unreviewed) / len(needs_revalidation)
        return ratio > self._ratio_threshold

    def check_finding_refs(
        self, finding_refs: dict[str, list[str]]
    ) -> bool:
        """检查 finding 是否涉及需求章(1-3)或方案概览(4.1)。

        finding_refs: finding_id → spec_refs 列表
        """
        for refs in finding_refs.values():
            for ref in refs:
                if self._is_major_ref(ref):
                    return True
        return False

    @staticmethod
    def _is_major_ref(ref: str) -> bool:
        """检查 ref 是否是需求章(1-3)或方案概览(4.1)。"""
        if ref == "4.1":
            return True
        return ref.startswith(_MAJOR_SPEC_PREFIXES)

    def check_consecutive_failures(self, failure_rounds: int) -> bool:
        """检查连续失败轮次是否到阈值。"""
        return failure_rounds >= self._consecutive_failures

    def detect(
        self,
        needs_revalidation: list[str],
        reviewed: list[str],
        finding_refs: dict[str, list[str]],
        consecutive_failures: int,
    ) -> UpgradeDecision:
        """综合判定是否需要升级（任一触发条件满足即升级）。"""
        reasons: list[str] = []

        if self.check_ratio(needs_revalidation, reviewed):
            unreviewed = len(set(needs_revalidation) - set(reviewed))
            ratio = (
                unreviewed / len(needs_revalidation)
                if needs_revalidation
                else 0
            )
            reasons.append(
                f"needs_revalidation 未审占比 {ratio:.0%} > 阈值"
                f" {self._ratio_threshold:.0%}"
            )

        if self.check_finding_refs(finding_refs):
            reasons.append("finding 涉及需求章(1-3)或方案概览(4.1)")

        if self.check_consecutive_failures(consecutive_failures):
            reasons.append(
                f"连续 {consecutive_failures} 轮同类失败"
                f" >= 阈值 {self._consecutive_failures}"
            )

        return UpgradeDecision(
            should_upgrade=len(reasons) > 0,
            reasons=reasons,
        )
