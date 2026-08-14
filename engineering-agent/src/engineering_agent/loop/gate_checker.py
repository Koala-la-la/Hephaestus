"""硬关卡校验器。

design doc §8.1（基本单元的「客观验证」部分）+
§5.3 铁律1（硬关卡必须能映射到 manifest 字段）。

GateChecker 读 manifest 字段 → 判条件 → PASS/FAIL。
批量校验——有 FAIL 则整体 FAIL。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from engineering_agent.manifest.store import ManifestStore


@dataclass
class GateCheck:
    """硬关卡定义。

    将一条硬关卡映射到 manifest 片+字段+判定条件（§5.3 铁律1）。
    """

    gate_id: str
    phase: str
    field: str
    condition: Callable[[Any], bool]
    description: str = ""


@dataclass
class GateResult:
    """单条硬关卡校验结果。"""

    gate_id: str
    passed: bool
    actual_value: Any
    description: str = ""


@dataclass
class BatchResult:
    """批量校验结果。

    all_pass=True 当且仅当所有 gate 都 PASS。
    failures 是未通过的子集。
    """

    results: list[GateResult] = field(default_factory=list)

    @property
    def all_pass(self) -> bool:
        """全过才 PASS。"""
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[GateResult]:
        """未通过的关卡。"""
        return [r for r in self.results if not r.passed]


# 编码阶段出口硬关卡清单（design doc §附录A 映射）
CODING_EXIT_GATES: list[GateCheck] = [
    GateCheck(
        "tasks_done", "phase3", "task_status_all_done",
        lambda v: v is True, "tasks 全 Completed",
    ),
    GateCheck(
        "lint_delta", "phase3", "lint_baseline_delta",
        lambda v: v == 0, "lint 0 新增",
    ),
    GateCheck(
        "compile", "phase3", "compile_passed",
        lambda v: v is True, "编译过",
    ),
    GateCheck(
        "test_regression", "phase3", "test_regression_passed",
        lambda v: v is True, "现有测试无 regression",
    ),
    GateCheck(
        "new_test", "phase3", "new_test_passed",
        lambda v: v is True, "新增单测过",
    ),
    GateCheck(
        "review", "phase3", "review_passed",
        lambda v: v is True, "review PASS",
    ),
    GateCheck(
        "traces", "phase3", "all_traces_exist",
        lambda v: v is True, "轨迹日志全",
    ),
]


class GateChecker:
    """硬关卡校验器。

    单条：check(gate, store) → 读 manifest 字段 → 判条件 → PASS/FAIL
    批量：check_all(gates, store) → 全过才 PASS，有 FAIL 则整体 FAIL
    """

    def check(self, gate: GateCheck, store: ManifestStore) -> GateResult:
        """单条校验：读 manifest 字段 → 判条件 → PASS/FAIL。"""
        value = store.get_field(gate.phase, gate.field)
        passed = gate.condition(value)
        return GateResult(
            gate_id=gate.gate_id,
            passed=passed,
            actual_value=value,
            description=gate.description,
        )

    def check_all(
        self, gates: list[GateCheck], store: ManifestStore
    ) -> BatchResult:
        """批量校验：全过才 PASS，有 FAIL 则整体 FAIL。"""
        results = [self.check(g, store) for g in gates]
        return BatchResult(results=results)
