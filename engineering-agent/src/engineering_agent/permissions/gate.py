"""工具权限拦截器。

design doc §6.3。在 Agent 调用工具前检查权限——
L0 放行 / L1 放行+audit / L2 拒绝+audit / L3 返回 need_confirm。

铁律2（§6.3）：L2 在 Harness 层直接禁——agent 根本看不到工具接口。
本类是 Harness 侧的兜底拦截点。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engineering_agent.manifest.models import SDLCPhase
from engineering_agent.permissions.levels import DangerLevel
from engineering_agent.permissions.matrix import PermissionMatrix


@dataclass
class PermissionResult:
    """权限检查结果。

    allowed=True → 可执行
    allowed=False → 不可执行（L2 拒绝 或 L3 需人确认）
    needs_confirm → L3，需等待 confirm token 才放行
    """

    allowed: bool
    danger_level: DangerLevel
    reason: str

    @property
    def needs_confirm(self) -> bool:
        """L3 需要人确认（design doc §6.1）。"""
        return self.danger_level == DangerLevel.L3


class ToolGate:
    """工具权限拦截器。

    在 Agent 调用工具前检查权限（design doc §6.3）。
    audit 日志只记 L1/L2/L3（L0 无害不记）。
    """

    def __init__(self, matrix: PermissionMatrix | None = None) -> None:
        self._matrix = matrix or PermissionMatrix()
        self._audit_log: list[dict[str, str]] = []

    def check_permission(
        self, phase: SDLCPhase | str, tool: str
    ) -> PermissionResult:
        """检查（阶段, 工具）的权限。

        L0 → 放行（不记 audit）
        L1 → 放行 + audit 日志
        L2 → 拒绝 + audit 日志（agent 看不到接口，这里是兜底）
        L3 → 返回 need_confirm + audit 日志
        """
        level = self._matrix.get_level(phase, tool)

        if level == DangerLevel.L0:
            # L0 无害，放行不记 audit
            return PermissionResult(
                allowed=True, danger_level=level, reason="L0 无害"
            )

        if level == DangerLevel.L1:
            self._log(phase, tool, level, "allowed", "L1 可逆")
            return PermissionResult(
                allowed=True, danger_level=level, reason="L1 可逆，有 audit"
            )

        if level == DangerLevel.L2:
            self._log(phase, tool, level, "denied", "L2 不可逆，Harness 直接禁")
            return PermissionResult(
                allowed=False,
                danger_level=level,
                reason="L2 不可逆，禁止",
            )

        # L3
        self._log(phase, tool, level, "need_confirm", "L3 需人确认")
        return PermissionResult(
            allowed=False,
            danger_level=level,
            reason="L3 需人确认，等待 confirm token",
        )

    def _log(
        self,
        phase: SDLCPhase | str,
        tool: str,
        level: DangerLevel,
        action: str,
        reason: str,
    ) -> None:
        """写 audit 日志（design doc §6.3 L1 有 audit 日志）。"""
        phase_str = phase.value if isinstance(phase, SDLCPhase) else phase
        self._audit_log.append(
            {
                "phase": phase_str,
                "tool": tool,
                "level": level.value,
                "action": action,
                "reason": reason,
            }
        )

    @property
    def audit_log(self) -> list[dict[str, str]]:
        """获取 audit 日志副本。"""
        return list(self._audit_log)

    def clear_audit_log(self) -> None:
        """清空 audit 日志。"""
        self._audit_log.clear()
