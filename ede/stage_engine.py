"""Stage Engine — pipeline orchestrator that manages the seven-phase workflow.

Spec §5.1:
  Each stage: PENDING → RUNNING → (DONE | BLOCKED | WAIT_USER)
  WAIT_USER → user confirms → RUNNING → DONE → next stage

The StageEngine drives the state machine, checks gates, and manages checkpoints.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable

from ede.models import Phase, TaskStatus, CheckpointStatus
from ede.state_machine import StateMachine, StageContext
from ede.gate_engine import GateEngine, GateResult


@dataclass
class Stage:
    """A single pipeline stage."""
    phase: Phase
    prerequisites: list[str] = field(default_factory=list)  # gate names required before start
    gates: list[str] = field(default_factory=list)
    run_fn: Optional[Callable] = None

    def has_human_checkpoint(self) -> bool:
        """Whether this stage requires user confirmation."""
        return StateMachine.needs_human_checkpoint(self.phase)


class StageEngine:
    """Orchestrates the seven-phase pipeline.

    Responsibilities:
      - Track current phase and status per task
      - Check prerequisites before starting a stage
      - Run gates after stage completion
      - Manage human checkpoints (WAIT_USER state)
      - Persist state to SQLite after every transition
    """

    def __init__(self, persistence, gate_engine: GateEngine):
        self.db = persistence
        self.gates = gate_engine
        self.sm = StateMachine()
        self._stages: dict[Phase, Stage] = {}

    def register_stage(self, stage: Stage) -> None:
        """Register a pipeline stage."""
        self._stages[stage.phase] = stage

    # ── Pipeline control ──────────────────────────────

    def advance(self, task_id: str) -> dict:
        """Advance the task to the next valid state.

        Returns a status dict describing what happened.
        """
        task = self.db.get_task(task_id)
        if task is None:
            return {"ok": False, "error": f"Task {task_id} not found"}

        phase = Phase(task["phase"])
        status = TaskStatus(task["status"])
        stage = self._stages.get(phase)

        if status == TaskStatus.PENDING:
            return self._start_stage(task_id, phase, stage)

        elif status == TaskStatus.WAIT_USER:
            return {"ok": False, "error": f"Task {task_id} is waiting for user confirmation. Use `ede confirm {phase.value}`."}

        elif status == TaskStatus.BLOCKED:
            return self._retry_blocked(task_id, phase, stage)

        elif status == TaskStatus.DONE:
            return self._move_to_next_stage(task_id, phase)

        elif status == TaskStatus.RUNNING:
            return {"ok": False, "error": f"Task {task_id} is already running."}

        return {"ok": False, "error": f"Unknown status: {status}"}

    def confirm(self, task_id: str, stage_name: str) -> dict:
        """User confirms a human checkpoint, unblocking the pipeline."""
        task = self.db.get_task(task_id)
        if task is None:
            return {"ok": False, "error": f"Task {task_id} not found"}

        status = TaskStatus(task["status"])
        phase = Phase(task["phase"]) if task["phase"] else None

        if status != TaskStatus.WAIT_USER:
            return {"ok": False, "error": f"Task {task_id} is not waiting for confirmation (status={status.value})"}

        if phase and phase.value != stage_name:
            return {"ok": False, "error": f"Task is at phase '{phase.value}', not '{stage_name}'"}

        # Update checkpoint
        now = datetime.now(timezone.utc).isoformat()
        self.db.update_checkpoint(task_id, stage_name, CheckpointStatus.CONFIRMED.value, now)

        # Move to DONE, then advance
        self.db.update_task(task_id, status=TaskStatus.DONE.value, updated_at=now)
        self.db.write_audit(task_id, "checkpoint_confirmed", f"User confirmed {stage_name}")

        return self._move_to_next_stage(task_id, phase)

    # ── Internal transitions ──────────────────────────

    def _start_stage(self, task_id: str, phase: Phase, stage: Optional[Stage]) -> dict:
        """Check prerequisites and start the stage."""
        if stage is None:
            return {"ok": False, "error": f"No stage registered for phase: {phase.value}"}

        # Check prerequisites
        if stage.prerequisites:
            results = self.gates.run_gates(stage.prerequisites)
            failed = [r for r in results if not r.passed]
            if failed:
                self.db.update_task(task_id, status=TaskStatus.BLOCKED.value)
                self.db.write_audit(task_id, "blocked_prereqs", str([f.gate_name for f in failed]))
                return {"ok": False, "blocked": True, "failed_gates": [f.gate_name for f in failed]}

        # Start running
        now = datetime.now(timezone.utc).isoformat()
        self.db.update_task(task_id, status=TaskStatus.RUNNING.value, updated_at=now)
        self.db.write_audit(task_id, "stage_running", phase.value)
        if stage.run_fn is not None:
            stage.run_fn(task_id, phase)
        return self._complete_stage(task_id, phase, stage)

    def _complete_stage(self, task_id: str, phase: Phase, stage: Stage) -> dict:
        """Complete the stage: run gates, then decide next state."""
        now = datetime.now(timezone.utc).isoformat()

        # Run completion gates
        if stage.gates:
            results = self.gates.run_gates(stage.gates)
            failed = [r for r in results if not r.passed]
            if failed:
                # Check if any failure is L3 (immediate WAIT_USER)
                l3_failures = [f for f in failed if self._gate_level(f.gate_name) == 3]
                if l3_failures:
                    self.db.update_task(task_id, status=TaskStatus.WAIT_USER.value, updated_at=now)
                    self.db.write_audit(task_id, "l3_blocked", str([f.gate_name for f in l3_failures]))
                    return {"ok": True, "state": "wait_user", "phase": phase.value,
                            "reason": f"L3 gates failed: {[f.gate_name for f in l3_failures]}"}

                # L1/L2 failures — mark blocked
                self.db.update_task(task_id, status=TaskStatus.BLOCKED.value, updated_at=now)
                self.db.write_audit(task_id, "gates_failed", str([f.gate_name for f in failed]))
                return {"ok": False, "blocked": True, "failed_gates": [f.gate_name for f in failed]}

        # All gates passed
        if stage.has_human_checkpoint():
            # Set WAIT_USER + create checkpoint
            self.db.update_task(task_id, status=TaskStatus.WAIT_USER.value, updated_at=now)
            self.db.create_checkpoint(task_id, phase.value, CheckpointStatus.PENDING.value)
            return {"ok": True, "state": "wait_user", "phase": phase.value,
                    "message": f"Stage {phase.value} complete. Run `ede confirm {phase.value}` to proceed."}

        # No checkpoint needed — mark DONE
        self.db.update_task(task_id, status=TaskStatus.DONE.value, updated_at=now)
        return {"ok": True, "state": "done", "phase": phase.value}

    def _move_to_next_stage(self, task_id: str, current_phase: Phase) -> dict:
        """Move to the next phase."""
        next_phase = self.sm.next_phase(current_phase)
        if next_phase is None:
            return {"ok": True, "state": "terminal", "message": "Pipeline complete."}

        now = datetime.now(timezone.utc).isoformat()
        self.db.update_task(task_id, phase=next_phase.value, status=TaskStatus.PENDING.value, updated_at=now)
        self.db.write_audit(task_id, "phase_advanced", f"{current_phase.value} → {next_phase.value}")

        # Auto-advance into the next stage
        return self._start_stage(task_id, next_phase, self._stages.get(next_phase))

    def _retry_blocked(self, task_id: str, phase: Phase, stage: Optional[Stage]) -> dict:
        """Retry a blocked stage."""
        if stage is None:
            return {"ok": False, "error": f"No stage for phase: {phase.value}"}
        self.db.update_task(task_id, status=TaskStatus.PENDING.value)
        return self._start_stage(task_id, phase, stage)

    def _gate_level(self, name: str) -> int:
        """Get the level of a registered gate."""
        gate = self.gates._gates.get(name)
        return gate.level.value if gate else 0
