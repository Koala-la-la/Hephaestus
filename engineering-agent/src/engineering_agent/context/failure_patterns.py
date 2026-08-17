"""failure-patterns 存储 + 按标签检索。

design doc §10.5。从 Pull 升级为 Push——
Harness 按当前 Loop 形态生成标签组合搜好 Push 给 agent。
agent 不知道自己该搜什么（上下文决定性），Harness 按标签匹配更可靠。

标签结构化（module/error_type/severity/phase）+
内容自然语言（symptom/root_cause/fix）——
"索引结构化、内容可自然语言"原则。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FailurePattern:
    """一条 failure-pattern 记录。

    前 4 个字段是结构化标签（Harness 按标签检索），
    后 3 个是自然语言内容（agent 阅读理解）。
    """

    module: str
    error_type: str
    severity: str
    phase: str
    symptom: str = ""
    root_cause: str = ""
    fix: str = ""


class FailurePatternStore:
    """failure-patterns 存储 + 按标签检索。

    search 是 Harness 用的（Push 式——Harness 按当前 Loop 形态
    生成标签组合搜好 Push 给 agent，§10.5）。
    """

    def __init__(self) -> None:
        self._patterns: list[FailurePattern] = []

    def add(self, pattern: FailurePattern) -> None:
        """添加一条 failure-pattern。"""
        self._patterns.append(pattern)

    def search(
        self,
        module: str | None = None,
        error_type: str | None = None,
        severity: str | None = None,
        phase: str | None = None,
    ) -> list[FailurePattern]:
        """按标签匹配检索。非 None 的标签是过滤条件（AND 关系）。"""
        results: list[FailurePattern] = []
        for p in self._patterns:
            if module is not None and p.module != module:
                continue
            if error_type is not None and p.error_type != error_type:
                continue
            if severity is not None and p.severity != severity:
                continue
            if phase is not None and p.phase != phase:
                continue
            results.append(p)
        return results

    def all_patterns(self) -> list[FailurePattern]:
        """获取所有记录。"""
        return list(self._patterns)

    def count(self) -> int:
        """记录总数。"""
        return len(self._patterns)
