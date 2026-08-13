"""manifest 数据模型 — 六片结构化元数据。

对应 design doc §5.2。manifest 是 Harness 的唯一操作对象——
Harness 只读 manifest，不解析自然语言产物。

三条铁律（§5.3）：
1. 硬关卡必须能映射到 manifest 字段
2. 字段必须机器可读（布尔/数字/数组/对象，不能自然语言描述）
3. manifest 写入是阶段出口唯一凭证
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 枚举（design doc §5.2 / §6.1 / §8.4 / §9.2）
# ──────────────────────────────────────────────


class ChangeType(str, Enum):
    """spec 变更类型（design doc §7.2）。"""

    MINOR = "minor"
    MAJOR = "major"


class TaskStatus(str, Enum):
    """task 状态流转：Pending → InProgress → InReview → Completed/Superseded。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"


class FindingSource(str, Enum):
    """review finding 来源（design doc §9.2 三级分级拦截）。

    machine = 机器 P0（硬拦不可覆盖）；agent = agent P0（半硬人可覆盖）。
    """

    MACHINE = "machine"
    AGENT = "agent"


class FindingSeverity(str, Enum):
    """review finding 严重等级。"""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class LoopType(str, Enum):
    """Loop 形态类型（design doc §8.2 / §8.4 current_loop_type）。"""

    A = "A"  # 前进 Task Loop（单 agent 串行）
    B = "B"  # minor 刷新
    C = "C"  # major 刷新
    D = "D"  # needs_revalidation review
    E = "E"  # 灰度轮询
    GRAPH = "Graph"  # 多 agent 并行（review 阶段）


class SDLCPhase(str, Enum):
    """SDLC 阶段（design doc §4.1）。"""

    REQUIREMENT = "requirement"
    DESIGN = "design"
    CODING = "coding"
    TESTING = "testing"
    RELEASE = "release"


class GrayscaleStatus(str, Enum):
    """灰度状态（design doc §5.2 phase5）。"""

    PASS = "pass"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


# ──────────────────────────────────────────────
# 辅助模型
# ──────────────────────────────────────────────


class ThresholdSpec(BaseModel):
    """监控阈值规格（design doc §A5 结构化谓词）。

    Harness 直接读 op/value/unit 判「在阈值内」，不解析字符串。
    指标不发明——由阶段1 非功能 checklist 决定关注哪些维度。
    """

    metric: str
    op: Literal["<", ">", "<=", ">=", "=="]
    value: float | int | str
    unit: str


class TaskSpec(BaseModel):
    """task 规格（design doc §5.2 phase2.tasks[]）。

    spec_refs 由设计 agent 标注，Harness 按 spec_refs 精准 Push spec 相关章节。
    estimated_files 是软映射（glob 模式如 "auth/*"），Harness 用依赖分析硬兜底。
    """

    id: str
    spec_refs: list[str] = Field(default_factory=list)
    estimated_files: list[str] = Field(default_factory=list)
    estimated_loc: int | None = None
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    """review finding（design doc §5.2 phase3.review_findings[]）。

    source 字段咬合三级分级拦截：
    - machine + P0 → Harness 硬拦不可覆盖
    - agent + P0 → Harness 拦，人可显式覆盖（留痕）
    - P1/P2 → 记录不阻断
    """

    severity: FindingSeverity
    source: FindingSource
    file: str
    line: int | None = None
    fixed: bool = False


class LoopStateLocation(BaseModel):
    """loop_state 定位层（design doc §8.4）。

    回答「我在哪」——Harness 自动改，每次状态切换时更新。
    """

    current_phase: SDLCPhase
    current_task_id: str | None = None
    current_subtask: str | None = None
    current_loop_type: LoopType = LoopType.A


class LoopStateSnapshot(BaseModel):
    """loop_state 进度快照层（design doc §8.4）。

    回答「干了多少」。字段可靠性分两类：
    - 机器可验证（files_modified/review_round/revalidation_checked）：Harness 从客观源拉取
    - agent 上报（completed_steps 语义步骤）：有客观验证兜底
    """

    files_modified: list[str] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    review_round: int = 0
    pending_findings: list[str] = Field(default_factory=list)
    revalidation_checked: list[str] = Field(default_factory=list)


class LoopState(BaseModel):
    """loop_state 状态机现场（design doc §8.4）。

    边界：只存执行进度，不存执行结果。结果在 manifest 的 status 字段。
    review PASS 后 pending_findings 必须清空，判定转到 manifest.status。
    """

    location: LoopStateLocation
    snapshot: LoopStateSnapshot = Field(default_factory=LoopStateSnapshot)


# ──────────────────────────────────────────────
# 六片 manifest（design doc §5.2）
# ──────────────────────────────────────────────


class CommonManifest(BaseModel):
    """common 片 — 全阶段共享。

    manifest 和 spec 共享同一 Git SHA，不独立版本号（design doc §5.4）。
    """

    spec_sha: str
    spec_version: str
    change_type: ChangeType | None = None


class Phase1Manifest(BaseModel):
    """phase1 片 — 需求阶段产出。

    goal_measurable 由 Critic 写（机器粗筛谓词 + Critic 精判 + 人可覆盖）。
    """

    sections_status: dict[str, str] = Field(default_factory=dict)
    goal_measurable: bool = False
    goal_measurable_evidence: str = ""
    nonfunctional_checked: bool = False


class Phase2Manifest(BaseModel):
    """phase2 片 — 设计阶段产出。

    reverse_coverage 由 Harness 从 tasks 的 spec_refs 反推，不信 agent 维护。
    """

    sections_status: dict[str, str] = Field(default_factory=dict)
    tradeoff_count: int = 0
    monitoring_thresholds: dict[str, ThresholdSpec] = Field(default_factory=dict)
    rollback_plan_exists: bool = False
    tasks: list[TaskSpec] = Field(default_factory=list)
    reverse_coverage: dict[str, list[str]] = Field(default_factory=dict)


class Phase3Manifest(BaseModel):
    """phase3 片 — 编码阶段产出。

    needs_revalidation 只含改现有的文件（design doc §A3 新功能进 to_create）。
    loop_state 只存进度不存结果——review_passed 是判定，不在 loop_state。
    """

    task_status_all_done: bool = False
    lint_baseline_delta: int = 0
    compile_passed: bool = False
    test_regression_passed: bool = False
    new_test_passed: bool = False
    review_passed: bool = False
    review_findings: list[ReviewFinding] = Field(default_factory=list)
    needs_revalidation: list[str] = Field(default_factory=list)
    needs_revalidation_reviewed: list[str] = Field(default_factory=list)
    to_create: list[str] = Field(default_factory=list)
    created: list[str] = Field(default_factory=list)
    all_traces_exist: bool = False
    loop_state: LoopState | None = None


class Phase4Manifest(BaseModel):
    """phase4 片 — 测试阶段产出。"""

    all_tests_passed: bool = False
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    coverage_met: bool = False
    three_category_coverage: dict[str, bool] = Field(
        default_factory=lambda: {
            "happy_path": False,
            "boundary": False,
            "exception": False,
        }
    )
    test_report_structured: bool = False


class Phase5Manifest(BaseModel):
    """phase5 片 — 上线阶段产出。

    monitoring_thresholds 从 phase2 快照复制，灰度中不变（design doc §5.4）。
    Agent 不持生产写权限——grayscale推进需 confirm token（design doc §4.6）。
    """

    release_package_sha: str = ""
    rollback_plan: str = ""
    grayscale_strategy: list[int] = Field(default_factory=lambda: [5, 25, 50, 100])
    monitoring_thresholds: dict[str, ThresholdSpec] = Field(default_factory=dict)
    grayscale_current: int = 0
    grayscale_phase: str = ""
    grayscale_status: GrayscaleStatus = GrayscaleStatus.IN_PROGRESS
