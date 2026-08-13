"""manifest 包 — 结构化元数据的六片模型。

Harness 的唯一操作对象。Harness 只读 manifest，不解析自然语言产物。
对应 design doc §5。
"""

from engineering_agent.manifest.models import (
    # 枚举
    ChangeType,
    FindingSeverity,
    FindingSource,
    GrayscaleStatus,
    LoopType,
    SDLCPhase,
    TaskStatus,
    # 辅助模型
    LoopState,
    LoopStateLocation,
    LoopStateSnapshot,
    ReviewFinding,
    TaskSpec,
    ThresholdSpec,
    # 六片
    CommonManifest,
    Phase1Manifest,
    Phase2Manifest,
    Phase3Manifest,
    Phase4Manifest,
    Phase5Manifest,
)

__all__ = [
    # 枚举
    "ChangeType",
    "FindingSeverity",
    "FindingSource",
    "GrayscaleStatus",
    "LoopType",
    "SDLCPhase",
    "TaskStatus",
    # 辅助模型
    "LoopState",
    "LoopStateLocation",
    "LoopStateSnapshot",
    "ReviewFinding",
    "TaskSpec",
    "ThresholdSpec",
    # 六片
    "CommonManifest",
    "Phase1Manifest",
    "Phase2Manifest",
    "Phase3Manifest",
    "Phase4Manifest",
    "Phase5Manifest",
]
