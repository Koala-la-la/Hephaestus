"""L3 交互协议——三子协议解析。

design doc §11.2。
agent 每次输出必须是以下三种结构化 JSON 之一：
1. tool_call（调用工具）
2. step_output（step 产出，同时是轨迹日志记录）
3. task_complete（完成声明）

agent 不直接写 manifest——通过 manifest_update_request 请求，
Harness 交叉验证后写（防美化，§5.5）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """工具调用（子协议 1）。"""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepOutput:
    """step 产出（子协议 2）——同时是轨迹日志一条记录。

    manifest_update_request 是 agent 请求更新 manifest——
    Harness 校验后写（agent 不直接写 manifest，防美化）。
    """

    action: str
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    duration: int | None = None
    manifest_update_request: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskComplete:
    """完成声明（子协议 3）。

    Harness 收到后跑出口硬关卡校验（读 manifest 字段）。
    """

    id: str
    evidence: dict[str, Any] = field(default_factory=dict)


class L3Protocol:
    """三子协议解析器。

    parse_output 解析 agent 输出的 JSON，返回对应 dataclass。
    """

    @staticmethod
    def parse_output(json_str: str) -> ToolCall | StepOutput | TaskComplete:
        """解析 agent 输出。

        Raises:
            json.JSONDecodeError: JSON 无效
            ValueError: type 字段未知
        """
        data = json.loads(json_str)
        output_type = data.get("type")

        if output_type == "tool_call":
            return ToolCall(
                tool=data.get("tool", ""),
                args=data.get("args", {}),
            )
        if output_type == "step_output":
            return StepOutput(
                action=data.get("action", ""),
                input=data.get("input", {}),
                output=data.get("output", {}),
                duration=data.get("duration"),
                manifest_update_request=data.get("manifest_update_request", {}),
            )
        if output_type == "task_complete":
            return TaskComplete(
                id=data.get("id", ""),
                evidence=data.get("evidence", {}),
            )
        raise ValueError(
            f"未知输出类型: {output_type}，"
            f"必须是 tool_call/step_output/task_complete 之一"
        )
