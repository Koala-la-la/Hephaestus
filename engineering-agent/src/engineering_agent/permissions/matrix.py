"""阶段×工具权限矩阵。

design doc §6.2 + §6.4（action 清单）。
权限按「阶段 + 角色」组合，阶段切换时 Harness 自动收回（§6.3 铁律1）。

保守策略：未列出的工具默认 L2（不确定就禁，比放行安全）。
"""

from __future__ import annotations

from typing import Any

from engineering_agent.manifest.models import SDLCPhase
from engineering_agent.permissions.levels import DangerLevel

# 默认权限矩阵（design doc §6.2 + §6.4 action 清单）
# 格式: (phase_value, tool_name) -> DangerLevel
# 未列出的工具默认 L2（保守策略）
DEFAULT_MATRIX: dict[tuple[str, str], DangerLevel] = {
    # ── 需求阶段（引导者）—— 只读 ──
    (SDLCPhase.REQUIREMENT.value, "read_file"): DangerLevel.L0,
    (SDLCPhase.REQUIREMENT.value, "grep"): DangerLevel.L0,
    (SDLCPhase.REQUIREMENT.value, "glob"): DangerLevel.L0,
    (SDLCPhase.REQUIREMENT.value, "codebase_research"): DangerLevel.L0,

    # ── 设计阶段（协作者）—— 读 + 写 docs/design-docs/ ──
    (SDLCPhase.DESIGN.value, "read_file"): DangerLevel.L0,
    (SDLCPhase.DESIGN.value, "grep"): DangerLevel.L0,
    (SDLCPhase.DESIGN.value, "glob"): DangerLevel.L0,
    (SDLCPhase.DESIGN.value, "codebase_research"): DangerLevel.L0,
    (SDLCPhase.DESIGN.value, "write_file"): DangerLevel.L1,

    # ── 编码阶段（执行者）—— 读 + 写 src/tests/ + 本地执行 ──
    (SDLCPhase.CODING.value, "read_file"): DangerLevel.L0,
    (SDLCPhase.CODING.value, "grep"): DangerLevel.L0,
    (SDLCPhase.CODING.value, "glob"): DangerLevel.L0,
    (SDLCPhase.CODING.value, "codebase_research"): DangerLevel.L0,
    (SDLCPhase.CODING.value, "write_file"): DangerLevel.L1,
    (SDLCPhase.CODING.value, "edit_file"): DangerLevel.L1,
    (SDLCPhase.CODING.value, "run_test"): DangerLevel.L1,
    (SDLCPhase.CODING.value, "run_lint"): DangerLevel.L1,
    (SDLCPhase.CODING.value, "git_diff"): DangerLevel.L0,
    (SDLCPhase.CODING.value, "call_reviewer"): DangerLevel.L1,
    (SDLCPhase.CODING.value, "handoff"): DangerLevel.L0,

    # ── 测试阶段（测试者）—— 读 + 写 tests/ + 本地执行 ──
    (SDLCPhase.TESTING.value, "read_file"): DangerLevel.L0,
    (SDLCPhase.TESTING.value, "grep"): DangerLevel.L0,
    (SDLCPhase.TESTING.value, "glob"): DangerLevel.L0,
    (SDLCPhase.TESTING.value, "codebase_research"): DangerLevel.L0,
    (SDLCPhase.TESTING.value, "write_file"): DangerLevel.L1,
    (SDLCPhase.TESTING.value, "edit_file"): DangerLevel.L1,
    (SDLCPhase.TESTING.value, "run_test"): DangerLevel.L1,
    (SDLCPhase.TESTING.value, "run_benchmark"): DangerLevel.L1,
    (SDLCPhase.TESTING.value, "coverage_report"): DangerLevel.L1,

    # ── 上线阶段（编排者）—— 读 + 编排（不持生产写权限）──
    (SDLCPhase.RELEASE.value, "read_file"): DangerLevel.L0,
    (SDLCPhase.RELEASE.value, "pull_monitoring"): DangerLevel.L0,
    (SDLCPhase.RELEASE.value, "create_release_package"): DangerLevel.L1,
    (SDLCPhase.RELEASE.value, "call_ci_cd"): DangerLevel.L1,
    (SDLCPhase.RELEASE.value, "request_rollback"): DangerLevel.L1,
    (SDLCPhase.RELEASE.value, "request_confirm"): DangerLevel.L3,

    # L2 工具（kubectl/aws/生产凭据）不在矩阵列出——默认 L2 即禁
}


class PermissionMatrix:
    """阶段×工具权限矩阵。

    给定（阶段, 工具）查危险等级。未列出默认 L2（保守策略——§6.3 铁律2）。
    可从 JSON 配置加载（项目级覆盖默认矩阵）。
    """

    def __init__(
        self, matrix: dict[tuple[str, str], DangerLevel] | None = None
    ) -> None:
        self._matrix: dict[tuple[str, str], DangerLevel] = (
            dict(matrix) if matrix is not None else dict(DEFAULT_MATRIX)
        )

    def get_level(
        self, phase: SDLCPhase | str, tool: str
    ) -> DangerLevel:
        """查询（阶段, 工具）的危险等级。未列出默认 L2。"""
        phase_str = phase.value if isinstance(phase, SDLCPhase) else phase
        return self._matrix.get((phase_str, tool), DangerLevel.L2)

    def set_level(
        self, phase: SDLCPhase | str, tool: str, level: DangerLevel
    ) -> None:
        """设置（阶段, 工具）的危险等级。项目级覆盖时用。"""
        phase_str = phase.value if isinstance(phase, SDLCPhase) else phase
        self._matrix[(phase_str, tool)] = level

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> PermissionMatrix:
        """从 dict 加载矩阵（JSON 反序列化后）。

        格式: {"requirement,read_file": "L0", ...}
        """
        matrix: dict[tuple[str, str], DangerLevel] = {}
        for key, level_str in data.items():
            phase, tool = key.split(",", 1)
            matrix[(phase, tool)] = DangerLevel(level_str)
        return cls(matrix)

    def to_dict(self) -> dict[str, str]:
        """序列化为 dict（JSON 可存储）。"""
        return {
            f"{phase},{tool}": level.value
            for (phase, tool), level in self._matrix.items()
        }
