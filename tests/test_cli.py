"""Tests for EDE CLI — M0 acceptance criteria."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def test_ede_init_creates_dot_ede():
    """AC: `ede init "test"` creates .ede/ with state.db, context.yaml, ede_audit.log."""
    tmp = tempfile.mkdtemp(prefix="ede_test_")
    try:
        result = subprocess.run(
            ["python", "-m", "ede.cli", "init", "test-project"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"ede init failed: {result.stderr}"

        ede_dir = Path(tmp) / ".ede"
        assert ede_dir.is_dir(), ".ede/ directory not created"
        assert (ede_dir / "state.db").is_file(), "state.db not created"
        assert (ede_dir / "context.yaml").is_file(), "context.yaml not created"
        assert (ede_dir / "ede_audit.log").is_file(), "ede_audit.log not created"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_ede_init_twice_fails():
    """Running ede init when .ede/ exists should fail."""
    tmp = tempfile.mkdtemp(prefix="ede_test_")
    try:
        subprocess.run(
            ["python", "-m", "ede.cli", "init", "first"],
            cwd=tmp,
            capture_output=True,
        )
        result = subprocess.run(
            ["python", "-m", "ede.cli", "init", "second"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Second init should have failed"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_db_has_six_tables():
    """AC: SQLite database has all 6 tables from the schema."""
    tmp = tempfile.mkdtemp(prefix="ede_test_")
    try:
        subprocess.run(
            ["python", "-m", "ede.cli", "init", "schema-test"],
            cwd=tmp,
            capture_output=True,
        )
        from ede.persistence import Persistence
        db = Persistence(str(Path(tmp) / ".ede" / "state.db"))
        tables = db.get_tables()
        expected = {"project", "task", "checkpoint", "gate_result", "audit_log", "change_log", "sqlite_sequence"}
        assert set(tables) == expected, f"Tables mismatch: got {set(tables)}, expected {expected}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_models_import_clean():
    """All model enums and data classes import without error."""
    from ede.models import (
        Phase, TaskStatus, CheckpointStatus, IntentGroup, RiskLabel,
        Project, Task, Checkpoint, GateResult, AuditLog, ChangeLog,
        DDL_CREATE_TABLES,
    )
    # Phase order
    assert Phase.SPEC.value == "spec"
    assert Phase.MERGE.value == "merge"
    # Next phase
    assert Phase.next_phase(Phase.SPEC) == Phase.DESIGN
    assert Phase.next_phase(Phase.MERGE) is None


def test_state_machine_transitions():
    """State machine validates correct phase transitions."""
    from ede.state_machine import StateMachine, StageContext
    from ede.models import Phase, TaskStatus

    sm = StateMachine()
    # Phase transitions
    assert sm.next_phase(Phase.CODE) == Phase.TEST
    assert sm.is_terminal(Phase.MERGE)
    assert not sm.is_terminal(Phase.SPEC)

    # Status transitions
    assert sm.can_transition_to(TaskStatus.PENDING, TaskStatus.RUNNING)
    assert sm.can_transition_to(TaskStatus.RUNNING, TaskStatus.WAIT_USER)
    assert sm.can_transition_to(TaskStatus.WAIT_USER, TaskStatus.RUNNING)
    assert not sm.can_transition_to(TaskStatus.DONE, TaskStatus.RUNNING)

    # Human checkpoints
    assert sm.needs_human_checkpoint(Phase.SPEC)
    assert sm.needs_human_checkpoint(Phase.DESIGN)
    assert sm.needs_human_checkpoint(Phase.PLAN)
    assert not sm.needs_human_checkpoint(Phase.CODE)


def test_context_creation():
    """StageContext factory creates a valid initial context."""
    from ede.state_machine import StageContext
    from ede.models import Phase, TaskStatus

    ctx = StageContext.create("task-001")
    assert ctx.task_id == "task-001"
    assert ctx.phase == Phase.SPEC
    assert ctx.status == TaskStatus.PENDING
    assert ctx.updated_at != ""
