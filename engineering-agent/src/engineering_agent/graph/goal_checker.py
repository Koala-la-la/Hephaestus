"""目标可衡量性判定。

design doc §9.5。
机器层粗筛（目标含数字阈值/比较运算符）+ Critic 层精判（谓词是否真可测）。
本轮只做机器层粗筛。
"""

from __future__ import annotations

import re


class CriticGoalChecker:
    """目标可衡量性判定器。

    机器粗筛：检查目标是否含可验证谓词（数字阈值/比较运算符）。
    "P99 < 200ms" → True
    "性能要好" → False

    Critic 精判接口预留（需要 LLM 调用，本轮不实现）。
    """

    _NUMBER_WITH_UNIT = re.compile(
        r"\d+\.?\d*\s*(ms|s|秒|分钟|%|QPS|qps|req|MB|GB|KB|次|个|条|M|K)",
        re.IGNORECASE,
    )
    _COMPARISON = re.compile(r"[<>=≤≥]\s*\d")

    def machine_check(self, goal: str) -> bool:
        """机器粗筛：目标是否含可验证谓词。

        Returns:
            True = 含数字阈值/比较运算符（可衡量）
            False = 无量化指标（不可衡量）
        """
        has_threshold = bool(self._COMPARISON.search(goal))
        has_number_unit = bool(self._NUMBER_WITH_UNIT.search(goal))
        return has_threshold or has_number_unit

    def critic_check(self, goal: str) -> bool:
        """Critic 精判：谓词是否真可测。

        本轮不实现（需要 LLM 调用）。直接回退到 machine_check。
        """
        return self.machine_check(goal)
