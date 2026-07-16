"""Task state machine — manages phase transitions and status lifecycle.

Implements the state diagram from spec §5.1:
  PENDING → RUNNING → DONE / BLOCKED / WAIT_USER
  WAIT_USER → RUNNING (after user confirm)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable

from ede.models import Phase, TaskStatus, CheckpointStatus


# ── Phase transition rules ─────────────────────────────

PHASE_TRANSITIONS: dict[Phase, Optional[Phase]] = {
    Phase.SPEC: Phase.DESIGN,
    Phase.DESIGN: Phase.PLAN,
    Phase.PLAN: Phase.CODE,
    Phase.CODE: Phase.TEST,
    Phase.TEST: Phase.REVIEW,
    Phase.REVIEW: Phase.MERGE,
    Phase.MERGE: None,  # terminal
}

# Stages that require human confirmation before proceeding
HUMAN_CHECKPOINT_PHASES = {Phase.SPEC, Phase.DESIGN, Phase.PLAN}


@dataclass
class StageContext:
    """Immutable snapshot of the current pipeline stage state."""
    task_id: str
    phase: Phase
    status: TaskStatus
    stage_data: dict = field(default_factory=dict)
    updated_at: str = ""

    @classmethod
    def create(cls, task_id: str) -> "StageContext":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            task_id=task_id,
            phase=Phase.SPEC,
            status=TaskStatus.PENDING,
            updated_at=now,
        )


class StateMachine:
    """Encapsulates phase transition rules and status lifecycle.

    No side effects — pure logic.  Persistence is handled by the caller.
    """

    # ── Phase transitions ───────────────────────────────

    @staticmethod
    def next_phase(current: Phase) -> Optional[Phase]:
        """Return the next phase, or None if current is terminal."""
        return PHASE_TRANSITIONS.get(current)

    @staticmethod
    def is_terminal(phase: Phase) -> bool:
        return PHASE_TRANSITIONS.get(phase) is None

    # ── Status lifecycle ────────────────────────────────

    @staticmethod
    def can_transition_to(current: TaskStatus, target: TaskStatus) -> bool:
        """Check if a status transition is valid."""
        allowed = {
            TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.BLOCKED},
            TaskStatus.RUNNING: {
                TaskStatus.DONE,
                TaskStatus.BLOCKED,
                TaskStatus.WAIT_USER,
            },
            TaskStatus.WAIT_USER: {TaskStatus.RUNNING, TaskStatus.DONE},
            TaskStatus.BLOCKED: {TaskStatus.PENDING, TaskStatus.WAIT_USER},
            TaskStatus.DONE: set(),  # terminal
        }
        return target in allowed.get(current, set())

    # ── Human checkpoints ───────────────────────────────

    @staticmethod
    def needs_human_checkpoint(phase: Phase) -> bool:
        """Whether this phase requires user confirmation before proceeding."""
        return phase in HUMAN_CHECKPOINT_PHASES
