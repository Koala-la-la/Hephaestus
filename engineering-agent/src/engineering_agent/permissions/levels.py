"""工具危险等级定义。

design doc §6.1。核心原则：L2 在 Harness 层直接禁——
agent 根本看不到工具接口，不是「提示不许用」（§6.3 铁律2）。
"""

from __future__ import annotations

from enum import Enum


class DangerLevel(str, Enum):
    """工具危险等级（design doc §6.1）。

    L0 无害：读文件/搜索/代码调研/拉监控 — Agent 可随时调
    L1 可逆：写文件(按路径)/跑测试/创建发布包/触发CI — Agent 可调，有 audit 日志
    L2 不可逆：kubectl apply/aws deploy/生产凭据 — Harness 直接禁（agent 看不到接口）
    L3 需人确认：灰度 25%+ 推进 — confirm token 触发
    """

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
