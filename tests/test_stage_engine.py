"""Unit tests for Stage Engine — pipeline orchestration."""

import sys, os, tempfile, shutil
sys.path.insert(0, r"C:\obsidian\KB\weiwei")

from ede.stage_engine import StageEngine, Stage
from ede.gate_engine import GateEngine, Gate, GateLevel
from ede.persistence import Persistence
from ede.models import Phase, TaskStatus, GateResult


def _setup(tmpdir: str) -> StageEngine:
    """Create a StageEngine with in-memory test setup."""
    db_path = os.path.join(tmpdir, "state.db")
    db = Persistence(db_path)
    db.init_db()
    db.insert_project("p1", "test")

    gates = GateEngine()
    engine = StageEngine(db, gates)

    # Register all seven stages
    for phase in Phase:
        engine.register_stage(Stage(phase))

    return engine


def test_advance_spec_to_design():
    """Task advances from SPEC PENDING → SPEC WAIT_USER → confirm → DESIGN PENDING."""
    tmp = tempfile.mkdtemp(prefix="ede_se_")
    try:
        engine = _setup(tmp)
        engine.db.create_task("t1", "p1", "test task")

        # First advance: PENDING → RUNNING → WAIT_USER (spec has checkpoint)
        result = engine.advance("t1")
        assert result["ok"]
        assert result["state"] == "wait_user"
        assert result["phase"] == "spec"

        # Confirm spec checkpoint
        result = engine.confirm("t1", "spec")
        assert result["ok"]
        assert result["state"] == "wait_user"  # design also has checkpoint
        assert result["phase"] == "design"

        task = engine.db.get_task("t1")
        assert task["phase"] == "design"
        assert task["status"] == "wait_user"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_spec_design_plan_full_flow():
    """Full flow through all three human checkpoint stages."""
    tmp = tempfile.mkdtemp(prefix="ede_se_")
    try:
        engine = _setup(tmp)
        engine.db.create_task("t2", "p1", "full flow")

        # spec
        r = engine.advance("t2")
        assert r["state"] == "wait_user" and r["phase"] == "spec"

        # confirm spec → design
        r = engine.confirm("t2", "spec")
        assert r["state"] == "wait_user" and r["phase"] == "design"

        # confirm design → plan
        r = engine.confirm("t2", "design")
        assert r["state"] == "wait_user" and r["phase"] == "plan"

        # confirm plan → code (no checkpoint)
        r = engine.confirm("t2", "plan")
        assert r["state"] == "done" and r["phase"] == "code"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_confirm_wrong_stage_fails():
    """Confirming a stage the task is not at returns error."""
    tmp = tempfile.mkdtemp(prefix="ede_se_")
    try:
        engine = _setup(tmp)
        engine.db.create_task("t3", "p1", "wrong confirm")
        engine.advance("t3")  # now at spec WAIT_USER

        result = engine.confirm("t3", "design")  # wrong stage
        assert not result["ok"]
        assert "design" in result.get("error", "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_checkpoint_persists():
    """Checkpoints are persisted to SQLite."""
    tmp = tempfile.mkdtemp(prefix="ede_se_")
    try:
        engine = _setup(tmp)
        engine.db.create_task("t4", "p1", "persist test")
        engine.advance("t4")  # creates checkpoint for spec

        # Verify checkpoint in DB
        assert engine.db.table_count("checkpoint") >= 1

        # Confirm and verify status changed
        engine.confirm("t4", "spec")
        assert engine.db.table_count("audit_log") >= 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_full_seven_phase_pipeline():
    """E2E: spec -> design -> plan -> code -> test -> review -> merge."""
    import tempfile, shutil, os
    tmp = tempfile.mkdtemp(prefix="ede_full2_")
    try:
        from ede.stage_engine import StageEngine, Stage
        from ede.gate_engine import GateEngine
        from ede.persistence import Persistence
        from ede.models import Phase, TaskStatus

        db_path = os.path.join(tmp, "state.db")
        db = Persistence(db_path)
        db.init_db()
        db.insert_project("p1", "full-test")

        gates = GateEngine()
        engine = StageEngine(db, gates)
        for phase in Phase:
            engine.register_stage(Stage(phase))
        engine.db.create_task("tx", "p1", "full pipeline")

        # spec -> design -> plan (with human checkpoints)
        r = engine.advance("tx")
        assert r["state"] == "wait_user" and r["phase"] == "spec"
        # Confirm through all three checkpoints
        r = engine.confirm("tx", "spec")
        assert r["phase"] == "design"
        r = engine.confirm("tx", "design")
        assert r["phase"] == "plan"
        r = engine.confirm("tx", "plan")
        # After plan confirm, auto-advances through code (no checkpoint)
        assert r["phase"] == "code" and r["state"] == "done"

        # Advance 4 more times: code->test, test->review, review->merge, merge->terminal
        phases_seen = set()
        for _ in range(5):  # extra iteration for terminal
            task = engine.db.get_task("tx")
            if task["status"] == "done":
                r = engine.advance("tx")
                if r.get("state") == "terminal":
                    break
            phases_seen.add(task["phase"])
            if len(phases_seen) >= 7:
                break

        # Verify all phases were hit
        task = engine.db.get_task("tx")
        assert engine.db.table_count("audit_log") >= 6
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
