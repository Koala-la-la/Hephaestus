"""多 agent Context 路由。

design doc §9.4。
共享层（所有 reviewer 都看到）+ 维度子集（按角色定制）。
两种极端都错：全共享→Token爆炸；全隔离→丢失交叉线索。
"""

from __future__ import annotations

# 5 个 reviewer 角色（design doc §9.3）
REVIEWER_ROLES = frozenset({
    "performance", "robustness", "standards",
    "spec-compliance", "contract-trust",
})

# 共享层——所有 reviewer 都看到的
SHARED_LAYER = frozenset({
    "spec_sections", "tasks_current", "diff", "applicable_norms",
})

# 维度子集——按 reviewer 角色定制
REVIEWER_DIMENSIONS: dict[str, frozenset[str]] = {
    "performance": frozenset({"hot_path_code", "performance_norms"}),
    "robustness": frozenset({"error_handling", "resource_norms"}),
    "standards": frozenset({"naming_rules", "full_files"}),
    "spec-compliance": frozenset({"spec_full", "implementation_compare"}),
    "contract-trust": frozenset({"contract_resources", "caller_trust_chain"}),
}


class ReviewerContextRouter:
    """多 agent Context 路由器。

    共享层 Push 给所有 reviewer，维度子集按角色定制。
    """

    def get_shared_layer(self) -> list[str]:
        """共享层——所有 reviewer 都看到的。"""
        return sorted(SHARED_LAYER)

    def get_dimension_subset(self, reviewer: str) -> list[str]:
        """维度子集——按 reviewer 角色定制。"""
        return sorted(REVIEWER_DIMENSIONS.get(reviewer, frozenset()))

    def get_all_for_reviewer(self, reviewer: str) -> list[str]:
        """获取 reviewer 的完整上下文（共享层 + 维度子集）。"""
        return self.get_shared_layer() + self.get_dimension_subset(reviewer)

    @staticmethod
    def get_all_reviewers() -> list[str]:
        """所有 reviewer 角色。"""
        return sorted(REVIEWER_ROLES)
