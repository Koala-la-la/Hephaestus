"""Push/Pull 上下文配置表。

design doc §10.1/§10.2。
Push = harness 强制注入（必须看到的，漏了就出错）
Pull = agent 按需拉（展开更好，不展开也能干活）
默认 Pull——不灌无关信息，比"默认 Push"安全。
"""

from __future__ import annotations

# 7 类上下文（design doc §10.2）
CONTEXT_TYPES = frozenset({
    "identity", "task_spec", "code", "norms",
    "history", "feedback", "baseline",
})

# Push 条目（design doc §10.2 矩阵）。未列出的默认 Pull。
PUSH_CONTEXTS: frozenset[tuple[str, str]] = frozenset({
    # identity — 全阶段 Push
    ("requirement", "identity"), ("design", "identity"),
    ("coding", "identity"), ("testing", "identity"), ("release", "identity"),
    # task_spec — 全阶段 Push
    ("requirement", "task_spec"), ("design", "task_spec"),
    ("coding", "task_spec"), ("testing", "task_spec"), ("release", "task_spec"),
    # norms — 需求 Push（非功能 checklist）、编码 Push（bp-coding 必加载）
    ("requirement", "norms"), ("coding", "norms"),
    # feedback — 全阶段 Push（只留最新）
    ("requirement", "feedback"), ("design", "feedback"),
    ("coding", "feedback"), ("testing", "feedback"), ("release", "feedback"),
    # baseline — 编码/测试/上线 Push（冻结基线）
    ("coding", "baseline"), ("testing", "baseline"), ("release", "baseline"),
})


class ContextMatrix:
    """Push/Pull 配置表。

    给定（阶段, 上下文类）查 push/pull。默认 Pull（不灌无关信息）。
    """

    def get_mode(self, phase: str, context_type: str) -> str:
        """查询注入方式。Returns "push" 或 "pull"。"""
        return "push" if (phase, context_type) in PUSH_CONTEXTS else "pull"

    def get_push_types(self, phase: str) -> list[str]:
        """获取指定阶段所有需要 Push 的上下文类。"""
        return sorted(ct for (p, ct) in PUSH_CONTEXTS if p == phase)

    def get_pull_types(self, phase: str) -> list[str]:
        """获取指定阶段所有需要 Pull 的上下文类。"""
        push = set(self.get_push_types(phase))
        return sorted(CONTEXT_TYPES - push)
