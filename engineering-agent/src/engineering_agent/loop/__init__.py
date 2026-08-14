"""loop 包 — 硬关卡校验 + 状态机现场 + 升级判定。

design doc §8（Loop 层）。
"""

from engineering_agent.loop.gate_checker import (
    CODING_EXIT_GATES,
    BatchResult,
    GateCheck,
    GateChecker,
    GateResult,
)
from engineering_agent.loop.state_tracker import LoopStateTracker
from engineering_agent.loop.upgrade_detector import (
    UpgradeDecision,
    UpgradeDetector,
)

__all__ = [
    "CODING_EXIT_GATES",
    "BatchResult",
    "GateCheck",
    "GateChecker",
    "GateResult",
    "LoopStateTracker",
    "UpgradeDecision",
    "UpgradeDetector",
]
