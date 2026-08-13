"""Harness 集成入口。

把 ManifestStore + ToolGate + SpecLock 串起来（design doc §4.4 决策1）。
manifest 是 Harness 唯一操作对象——Agent 通过 L3 协议请求，Harness 校验后执行。

spec-first 检查（§3.4 原则1）：编码阶段的写操作，必须先冻结 spec 才放行——
无 spec 不许改代码。这是把 Prompt 级「禁止无 spec 改代码」下沉到机制层的执行点。
"""

from __future__ import annotations

from pathlib import Path

from engineering_agent.manifest.store import ManifestStore
from engineering_agent.permissions.gate import PermissionResult, ToolGate
from engineering_agent.spec.lock import SpecLock

# 编码/测试阶段的写操作工具——需要 spec 先冻结才放行
_WRITE_TOOLS = frozenset({"edit_file", "write_file"})
_SPEC_FIRST_PHASES = frozenset({"coding", "testing"})


class Harness:
    """Harness 集成入口。

    集成三块核心功能：
    - ManifestStore：manifest 读写（§5）
    - ToolGate：工具权限拦截（§6）
    - SpecLock：spec SHA 锁定（§7.1）

    design doc §4.4 决策1：manifest 是 Harness 唯一操作对象。
    """

    def __init__(
        self,
        manifest_dir: Path | str,
        repo_root: Path | str | None = None,
    ) -> None:
        self.manifest_store = ManifestStore(manifest_dir)
        self.tool_gate = ToolGate()
        self.spec_lock = SpecLock(repo_root)
        self._frozen_spec_sha: str | None = None

    def freeze_spec(self, spec_path: Path | str) -> str:
        """冻结 spec SHA。未 commit 抛 RuntimeError。

        冻结后，编码阶段的写操作才会被放行（spec-first 规则）。
        """
        sha = self.spec_lock.freeze(spec_path)
        self._frozen_spec_sha = sha
        return sha

    @property
    def spec_frozen(self) -> bool:
        """spec 是否已冻结。"""
        return self._frozen_spec_sha is not None

    @property
    def frozen_spec_sha(self) -> str | None:
        """当前冻结的 spec SHA（未冻结返回 None）。"""
        return self._frozen_spec_sha

    def check_tool_permission(
        self,
        phase: str,
        tool: str,
    ) -> PermissionResult:
        """检查工具权限。

        两层检查：
        1. 权限矩阵（ToolGate）：L2 拒绝、L3 需确认、L0/L1 放行
        2. spec-first 检查：编码/测试阶段的写操作，必须先冻结 spec
           ——无 spec 不许改代码（§3.4 原则1）

        L2/L3 在权限层就被拒，不会走到 spec-first 检查。
        """
        # 第一层：权限矩阵
        result = self.tool_gate.check_permission(phase, tool)
        if not result.allowed:
            return result

        # 第二层：spec-first 检查（只对编码/测试阶段的写操作）
        if phase in _SPEC_FIRST_PHASES and tool in _WRITE_TOOLS:
            if not self.spec_frozen:
                return PermissionResult(
                    allowed=False,
                    danger_level=result.danger_level,
                    reason="spec 未冻结，无 spec 不许改代码（§3.4 原则1）",
                )

        return result

    def update_manifest_field(
        self, phase: str, field: str, value: object
    ) -> None:
        """更新 manifest 字段（Harness 专用，design doc §5.5）。"""
        self.manifest_store.update_field(phase, field, value)

    def get_manifest_field(self, phase: str, field: str) -> object:
        """读 manifest 字段。"""
        return self.manifest_store.get_field(phase, field)
