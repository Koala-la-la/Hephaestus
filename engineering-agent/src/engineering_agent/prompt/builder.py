"""Prompt 三子层组装器。

design doc §11.1。
L1 系统身份（固定模板，Harness 按阶段加载，替换不追加）
L2 当前任务说明（Harness 从 manifest 自动生成）
L3 交互协议（固定模板，常驻 < 500 token）

L1 的权限边界说明是软告知——真正的硬拦在 Harness 层（ToolGate）。
"""

from __future__ import annotations

from dataclasses import dataclass

from engineering_agent.manifest.store import ManifestStore

# L1 身份模板（5 阶段各一个角色描述）
L1_IDENTITY: dict[str, str] = {
    "requirement": (
        "你是需求引导者（苏格拉底式）。职责是引导用户将模糊意图显式化为 spec。"
        "权限边界：只读（read_file/grep/glob/codebase_research），不能写代码。"
    ),
    "design": (
        "你是设计协作者（用户主导）。职责是提供思考框架、质疑风险、用户请求时给建议。"
        "权限边界：读 + 写 docs/design-docs/，不能写代码。"
    ),
    "coding": (
        "你是代码执行者。职责是按 spec + tasks.md 逐 Task 实现代码。"
        "权限边界：读 + 写 src/tests/ + 本地执行，禁止无 spec 改代码。"
    ),
    "testing": (
        "你是测试者。职责是基于 spec 测试计划生成测试。"
        "权限边界：读 + 写 tests/ + 本地执行。"
    ),
    "release": (
        "你是上线编排者（不持生产写权限）。职责是产出发布包 + 编排灰度。"
        "权限边界：读 + 创建包 + 触发 CI/CD + 请求回滚，禁止 kubectl/生产凭据。"
    ),
}

# L3 协议骨架（常驻，简要）
L3_PROTOCOL = """输出协议（每次输出必须是以下三种 JSON 之一）：
1. {"type":"tool_call","tool":"<action>","args":{...}}
2. {"type":"step_output","action":"<action>","input":{...},"output":{...},"manifest_update_request":{...}}
3. {"type":"task_complete","id":"<task_id>","evidence":{...}}
"""


@dataclass
class PromptResult:
    """组装后的 Prompt 三子层。"""

    l1_identity: str
    l2_task_spec: str
    l3_protocol: str


class PromptBuilder:
    """Prompt 三子层组装器。L1/L3 固定，L2 从 manifest 生成。"""

    def build_prompt(
        self, phase: str, manifest_store: ManifestStore
    ) -> PromptResult:
        """组装 Prompt 三子层。"""
        return PromptResult(
            l1_identity=L1_IDENTITY.get(phase, ""),
            l2_task_spec=self._build_l2(phase, manifest_store),
            l3_protocol=L3_PROTOCOL,
        )

    @staticmethod
    def _build_l2(phase: str, manifest_store: ManifestStore) -> str:
        """从 manifest 生成 L2 任务说明。"""
        parts = [f"当前阶段：{phase}"]

        spec_sha = manifest_store.get_field("common", "spec_sha")
        if spec_sha:
            parts.append(f"spec 版本：{spec_sha}")

        tasks_data = manifest_store.read("phase2")
        if tasks_data and "tasks" in tasks_data:
            for t in tasks_data["tasks"]:
                if t.get("status") == "pending":
                    parts.append(f"当前 Task：{t.get('id', '?')}")
                    if t.get("spec_refs"):
                        parts.append(f"spec_refs：{t['spec_refs']}")
                    break

        needs = manifest_store.get_field("phase3", "needs_revalidation")
        if needs:
            parts.append(f"needs_revalidation：{needs}")

        return " | ".join(parts)

    def get_l1(self, phase: str) -> str:
        """获取 L1 身份模板。"""
        return L1_IDENTITY.get(phase, "")

    @staticmethod
    def get_l3() -> str:
        """获取 L3 协议骨架。"""
        return L3_PROTOCOL
