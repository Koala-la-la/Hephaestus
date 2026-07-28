"""Stage Engine — pipeline orchestrator (async version).

v0.3: All pipeline methods are now async (spec C-006).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

from ede.models import Phase, TaskStatus, CheckpointStatus
from ede.state_machine import StateMachine, StageContext
from ede.gate_engine import GateEngine, GateResult
from ede.context_engine import TrustConfig


@dataclass
class Stage:
    """A single pipeline stage."""
    phase: Phase
    prerequisites: list[str] = field(default_factory=list)
    gates: list[str] = field(default_factory=list)
    run_fn: Optional[Callable[..., Awaitable[None]]] = None

    def has_human_checkpoint(self) -> bool:
        return StateMachine.needs_human_checkpoint(self.phase)


class StageEngine:
    """Orchestrates the seven-phase pipeline (async)."""

    def __init__(self, persistence, gate_engine: GateEngine, trust_config: TrustConfig = None):
        self.db = persistence
        self.gates = gate_engine
        self.trust = trust_config or TrustConfig()
        self.sm = StateMachine()
        self._stages: dict[Phase, Stage] = {}
        self._reviewer = None

    def register_stage(self, stage: Stage) -> None:
        self._stages[stage.phase] = stage

    def set_reviewer(self, reviewer_orchestrator) -> None:
        self._reviewer = reviewer_orchestrator

    # ── Pipeline control (async) ──────────────────────

    async def advance(self, task_id: str) -> dict:
        task = self.db.get_task(task_id)
        if task is None:
            return {"ok": False, "error": f"Task {task_id} not found"}

        phase = Phase(task["phase"])
        status = TaskStatus(task["status"])
        stage = self._stages.get(phase)

        if status == TaskStatus.PENDING:
            return await self._start_stage(task_id, phase, stage)
        elif status == TaskStatus.WAIT_USER:
            return {"ok": False, "error": f"Task {task_id} is waiting for user confirmation."}
        elif status == TaskStatus.BLOCKED:
            return await self._retry_blocked(task_id, phase, stage)
        elif status == TaskStatus.DONE:
            return await self._move_to_next_stage(task_id, phase)
        elif status == TaskStatus.RUNNING:
            return {"ok": False, "error": f"Task {task_id} is already running."}
        return {"ok": False, "error": f"Unknown status: {status}"}

    async def confirm(self, task_id: str, stage_name: str) -> dict:
        task = self.db.get_task(task_id)
        if task is None:
            return {"ok": False, "error": f"Task {task_id} not found"}

        status = TaskStatus(task["status"])
        phase = Phase(task["phase"]) if task["phase"] else None

        if status != TaskStatus.WAIT_USER:
            return {"ok": False, "error": f"Task {task_id} is not waiting for confirmation"}
        if phase and phase.value != stage_name:
            return {"ok": False, "error": f"Task is at phase '{phase.value}', not '{stage_name}'"}

        now = datetime.now(timezone.utc).isoformat()
        self.db.update_checkpoint(task_id, stage_name, CheckpointStatus.CONFIRMED.value, now)
        self.db.update_task(task_id, status=TaskStatus.DONE.value, updated_at=now)
        self.db.write_audit(task_id, "checkpoint_confirmed", f"User confirmed {stage_name}")
        return await self._move_to_next_stage(task_id, phase)

    # ── Internal transitions (async) ──────────────────

    async def _start_stage(self, task_id: str, phase: Phase, stage: Optional[Stage],
                           _retry_depth: int = 0) -> dict:
        if stage is None:
            return {"ok": False, "error": f"No stage registered for phase: {phase.value}"}

        task = self.db.get_task(task_id)
        depends_on = task.get("depends_on", "") if task else ""
        if depends_on:
            dep_task = self.db.get_task(depends_on)
            if dep_task is None:
                return {"ok": False, "error": f"Depends on task {depends_on} which does not exist"}
            if dep_task.get("status") != "done" or dep_task.get("phase") != "merge":
                return {"ok": False, "error": f"Depends on {depends_on} not complete"}

        if stage.prerequisites:
            results = await self.gates.run_gates(stage.prerequisites)
            for r in results:
                self.db.insert_gate_result(task_id, r.gate_name, r.passed, r.detail)
            failed = [r for r in results if not r.passed]
            if failed:
                self.db.update_task(task_id, status=TaskStatus.BLOCKED.value)
                self.db.write_audit(task_id, "blocked_prereqs", str([f.gate_name for f in failed]))
                return {"ok": False, "blocked": True, "failed_gates": [f.gate_name for f in failed]}

        now = datetime.now(timezone.utc).isoformat()
        self.db.update_task(task_id, status=TaskStatus.RUNNING.value, updated_at=now)
        self.db.write_audit(task_id, "stage_running", phase.value)
        if stage.run_fn is not None:
            await stage.run_fn(task_id, phase)
        return await self._complete_stage(task_id, phase, stage, _retry_depth)

    async def _complete_stage(self, task_id: str, phase: Phase, stage: Stage,
                              _retry_depth: int = 0) -> dict:
        now = datetime.now(timezone.utc).isoformat()

        if stage.gates:
            results = await self.gates.run_gates(stage.gates)
            for r in results:
                self.db.insert_gate_result(task_id, r.gate_name, r.passed, r.detail)
            # Non-blocking gates (e.g. coverage) never block — audit only.
            non_blocking = [r for r in results if not r.passed and not self._gate_blocking(r.gate_name)]
            if non_blocking:
                self.db.write_audit(task_id, "gate_non_blocking_failed",
                    str([r.gate_name for r in non_blocking]))
            failed = [r for r in results if not r.passed and self._gate_blocking(r.gate_name)]
            if failed:
                l3_failures = [f for f in failed if self._gate_level(f.gate_name) == 3]
                if l3_failures:
                    if self.trust.should_block_on_l3_failure(phase.value):
                        self.db.update_task(task_id, status=TaskStatus.WAIT_USER.value, updated_at=now)
                        self.db.write_audit(task_id, "l3_blocked", str([f.gate_name for f in l3_failures]))
                        return {"ok": True, "state": "wait_user", "phase": phase.value,
                                "reason": f"L3 gates failed: {[f.gate_name for f in l3_failures]}"}
                    else:
                        self.db.write_audit(task_id, "l3_notified", f"Tier {self.trust.effective_tier(phase.value)}: proceeding")

                tier = self.trust.effective_tier(phase.value)
                if tier in ("T2", "T3"):
                    max_retries = self.trust.max_auto_retries(phase.value, 2)
                    if _retry_depth >= max_retries:
                        self.db.write_audit(task_id, "gates_auto_retry_exhausted",
                            f"Tier {tier}: {_retry_depth} retries exhausted")
                    else:
                        self.db.write_audit(task_id, "gates_auto_retry",
                            f"Tier {tier}: retry {_retry_depth+1}/{max_retries}")
                        self.db.update_task(task_id, status=TaskStatus.PENDING.value, updated_at=now)
                        return await self._start_stage(task_id, phase, stage, _retry_depth + 1)
                self.db.update_task(task_id, status=TaskStatus.BLOCKED.value, updated_at=now)
                self.db.write_audit(task_id, "gates_failed", str([f.gate_name for f in failed]))
                return {"ok": False, "blocked": True, "failed_gates": [f.gate_name for f in failed]}

        # All gates passed — accuracy check for CODE phase
        if phase == Phase.CODE and self._reviewer is not None:
            try:
                import asyncio
                change_logs = self.db.get_change_logs(task_id)
                agent_assessment = ""
                for cl in change_logs:
                    agent_assessment += f"Summary: {cl.get('summary', '')}\n"
                    entries = self.db.get_change_entries(cl.get('change_id', ''))
                    if entries:
                        for e in entries:
                            agent_assessment += f"  File: {e.get('file_path', '')} Intent: {e.get('intent_group', '')} Risk: {e.get('agent_risk_label', '')}\n"
                    else:
                        agent_assessment += f"  Intent: {cl.get('intent_group', '')} Risk: {cl.get('risk_label', '')}\n"
                if agent_assessment:
                    import subprocess
                    try:
                        diff_result = subprocess.run(["git", "diff", "--unified=3"], capture_output=True, text=True, timeout=30)
                        diff_text = diff_result.stdout[:4000]
                    except Exception:
                        diff_text = "[diff unavailable]"
                    accuracy_report = await self._reviewer.review_accuracy(task_id, agent_assessment, diff_text)
                    if accuracy_report.total_errors > 0:
                        # Upgrade effective risk on all entries of the latest
                        # change logs — self-assessment is inaccurate (spec §AC-007).
                        for cl in change_logs:
                            for e in self.db.get_change_entries(cl.get("change_id", "")):
                                upgraded = {"low": "medium", "medium": "high", "high": "high"}.get(
                                    e.get("agent_risk_label", "low"), "medium")
                                self.db.update_change_entry_accuracy(
                                    e.get("entry_id", ""), "inaccurate", upgraded)
                        self.db.update_task(task_id, status=TaskStatus.WAIT_USER.value, updated_at=now)
                        self.db.write_audit(task_id, "accuracy_blocked",
                            f"{accuracy_report.total_errors} inaccuracies found. {accuracy_report.summary}")
                        return {"ok": True, "state": "wait_user", "phase": phase.value,
                                "message": f"Agent self-assessment INACCURATE ({accuracy_report.total_errors} errors). Human review MANDATORY."}
            except Exception:
                import logging
                logging.getLogger("ede.stage_engine").warning("Accuracy check failed, proceeding without it", exc_info=True)

        if stage.has_human_checkpoint():
            if self.trust.should_block_human_checkpoint(phase.value):
                self.db.update_task(task_id, status=TaskStatus.WAIT_USER.value, updated_at=now)
                self.db.create_checkpoint(task_id, phase.value, CheckpointStatus.PENDING.value)
                return {"ok": True, "state": "wait_user", "phase": phase.value,
                        "message": f"Stage {phase.value} complete. Run `ede confirm {phase.value}` to proceed."}
            else:
                self.db.write_audit(task_id, "auto_checkpoint", f"Tier {self.trust.effective_tier(phase.value)}: {phase.value} auto-passed")
                self.db.update_task(task_id, status=TaskStatus.DONE.value, updated_at=now)
                return {"ok": True, "state": "done", "phase": phase.value}

        self.db.update_task(task_id, status=TaskStatus.DONE.value, updated_at=now)
        return {"ok": True, "state": "done", "phase": phase.value}

    async def _move_to_next_stage(self, task_id: str, current_phase: Phase) -> dict:
        next_phase = self.sm.next_phase(current_phase)
        if next_phase is None:
            return {"ok": True, "state": "terminal", "message": "Pipeline complete."}
        now = datetime.now(timezone.utc).isoformat()
        self.db.update_task(task_id, phase=next_phase.value, status=TaskStatus.PENDING.value, updated_at=now)
        self.db.write_audit(task_id, "phase_advanced", f"{current_phase.value} → {next_phase.value}")
        return await self._start_stage(task_id, next_phase, self._stages.get(next_phase))

    async def _retry_blocked(self, task_id: str, phase: Phase, stage: Optional[Stage]) -> dict:
        if stage is None:
            return {"ok": False, "error": f"No stage for phase: {phase.value}"}
        self.db.update_task(task_id, status=TaskStatus.PENDING.value)
        return await self._start_stage(task_id, phase, stage)

    def _gate_level(self, name: str) -> int:
        gate = self.gates._gates.get(name)
        return gate.level.value if gate else 0

    def _gate_blocking(self, name: str) -> bool:
        gate = self.gates._gates.get(name)
        return gate.blocking if gate else True
