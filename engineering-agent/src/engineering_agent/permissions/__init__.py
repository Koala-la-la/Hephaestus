"""permissions 包 — 工具权限分级与拦截。

design doc §6。L2 在 Harness 层直接禁（agent 看不到接口）。
"""

from engineering_agent.permissions.gate import PermissionResult, ToolGate
from engineering_agent.permissions.levels import DangerLevel
from engineering_agent.permissions.matrix import DEFAULT_MATRIX, PermissionMatrix

__all__ = [
    "DangerLevel",
    "PermissionMatrix",
    "DEFAULT_MATRIX",
    "PermissionResult",
    "ToolGate",
]
