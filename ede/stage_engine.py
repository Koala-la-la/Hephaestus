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
from ede.context_engine import TrustConfig


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

    def __init__(self, persistence, gate_engine: GateEngine, trust_config: TrustConfig = None):
        self.db = persistence
        self.gates = gate_engine
        self.trust = trust_config or TrustConfig()
        self.sm = StateMachine()
        self._stages: dict[Phase, Stage] = {}
        self._reviewer = None  # injected by CLI for accuracy checks

    def register_stage(self, stage: Stage) -> None:
        """Register a pipeline stage."""
        self._stages[stage.phase] = stage

    def set_reviewer(self, reviewer_orchestrator) -> None:
        """Inject a ReviewerOrchestrator for accuracy checks after code stage."""
        self._reviewer = reviewer_orchestrator

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

    def _start_stage(self, task_id: str, phase: Phase, stage: Optional[Stage],
                     _retry_depth: int = 0) -> dict:
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
        return self._complete_stage(task_id, phase, stage, _retry_depth)

    def _complete_stage(self, task_id: str, phase: Phase, stage: Stage,
                        _retry_depth: int = 0) -> dict:
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
                    if self.trust.should_block_on_l3_failure(phase.value):
                        self.db.update_task(task_id, status=TaskStatus.WAIT_USER.value, updated_at=now)
                        self.db.write_audit(task_id, "l3_blocked", str([f.gate_name for f in l3_failures]))
                        return {"ok": True, "state": "wait_user", "phase": phase.value,
                                "reason": f"L3 gates failed: {[f.gate_name for f in l3_failures]}"}
                    else:
                        # T2+: notify but don't block
                        self.db.write_audit(task_id, "l3_notified", f"Tier {self.trust.effective_tier(phase.value)}: {[f.gate_name for f in l3_failures]} — proceeding")

                # L1/L2 failures — block or auto-retry (Trust-aware)
                tier = self.trust.effective_tier(phase.value)
                if tier in ("T2", "T3"):
                    max_retries = self.trust.max_auto_retries(phase.value, 2)
                    if _retry_depth >= max_retries:
                        self.db.write_audit(task_id, "gates_auto_retry_exhausted",
                            f"Tier {tier}: {_retry_depth} retries exhausted for {[f.gate_name for f in failed]}")
                    else:
                        self.db.write_audit(task_id, "gates_auto_retry",
                            f"Tier {tier}: retry {_retry_depth+1}/{max_retries} for {[f.gate_name for f in failed]}")
                        self.db.update_task(task_id, status=TaskStatus.PENDING.value, updated_at=now)
                        return self._start_stage(task_id, phase, stage, _retry_depth + 1)
                self.db.update_task(task_id, status=TaskStatus.BLOCKED.value, updated_at=now)
                self.db.write_audit(task_id, "gates_failed", str([f.gate_name for f in failed]))
                return {"ok": False, "blocked": True, "failed_gates": [f.gate_name for f in failed]}

        # All gates passed
        if stage.has_human_checkpoint():
            if self.trust.should_block_human_checkpoint(phase.value):
                # T0: block and wait
                self.db.update_task(task_id, status=TaskStatus.WAIT_USER.value, updated_at=now)
                self.db.create_checkpoint(task_id, phase.value, CheckpointStatus.PENDING.value)
                return {"ok": True, "state": "wait_user", "phase": phase.value,
                        "message": f"Stage {phase.value} complete. Run `ede confirm {phase.value}` to proceed."}
            else:
                # T1+: auto-pass, go to DONE
                self.db.write_audit(task_id, "auto_checkpoint", f"Tier {self.trust.effective_tier(phase.value)}: {phase.value} auto-passed")
                self.db.update_task(task_id, status=TaskStatus.DONE.value, updated_at=now)
                return {"ok": True, "state": "done", "phase": phase.value}

        # Accuracy check for CODE phase (Trust Tier cannot override)
        if phase == Phase.CODE and self._reviewer is not None:
            try:
                import asyncio
                # Collect agent self-assessment from change entries (preferred) or logs
                change_logs = self.db.get_change_logs(task_id)
                agent_assessment = ""
                for cl in change_logs:
                    agent_assessment += f"Summary: {cl.get('summary', '')}\n"
                    # Try to get per-file entries for richer assessment
                    entries = self.db.get_change_entries(cl.get('change_id', ''))
                    if entries:
                        for e in entries:
                            agent_assessment += (
                                f"  File: {e.get('file_path', '')} "
                                f"Intent: {e.get('intent_group', '')} "
                                f"Risk: {e.get('agent_risk_label', '')}\n"
                            )
                    else:
                        agent_assessment += (
                            f"  Intent: {cl.get('intent_group', '')} "
                            f"Risk: {cl.get('risk_label', '')}\n"
                        )
                if agent_assessment:
                    # Get diff from git
                    import subprocess
                    try:
                        diff_result = subprocess.run(
                            ["git", "diff", "--unified=3"],
                            capture_output=True, text=True, timeout=30,
                        )
                        diff_text = diff_result.stdout[:4000]
                    except Exception:
                        diff_text = "[diff unavailable]"
                    # Run accuracy review (async → sync)
                    loop = None
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    accuracy_report = loop.run_until_complete(
                        self._reviewer.review_accuracy(task_id, agent_assessment, diff_text)
                    )
                    if accuracy_report.total_errors > 0:
                        # Agent assessment inaccurate → force WAIT_USER
                        self.db.update_task(task_id, status=TaskStatus.WAIT_USER.value, updated_at=now)
                        self.db.write_audit(task_id, "accuracy_blocked",
                            f"{accuracy_report.total_errors} inaccuracies found. {accuracy_report.summary}")
                        return {
                            "ok": True, "state": "wait_user", "phase": phase.value,
                            "message": f"Agent self-assessment INACCURATE ({accuracy_report.total_errors} errors). "
                                       f"Human review MANDATORY. Run `ede confirm code` after review.",
                        }
            except Exception:
                import logging
                logging.getLogger("ede.stage_engine").warning(
                    "Accuracy check failed, proceeding without it", exc_info=True
                )

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
