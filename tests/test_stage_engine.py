"""Unit tests for Stage Engine — pipeline orchestration (async)."""

import sys, os, tempfile, shutil, asyncio
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

from ede.stage_engine import StageEngine, Stage
from ede.gate_engine import GateEngine, Gate, GateLevel
from ede.persistence import Persistence
from ede.models import Phase, TaskStatus, GateResult
from ede.context_engine import TrustConfig


def _setup(tmpdir: str) -> StageEngine:
    db_path = os.path.join(tmpdir, "state.db")
    db = Persistence(db_path)
    db.init_db()
    db.insert_project("p1", "test")
    gates = GateEngine()
    engine = StageEngine(db, gates, TrustConfig(tier="T0"))
    for phase in Phase:
        engine.register_stage(Stage(phase))
    return engine


def test_advance_spec_to_design():
    tmp = tempfile.mkdtemp(prefix="ede_se_")
    try:
        engine = _setup(tmp)
        engine.db.create_task("t1", "p1", "test task")
        result = asyncio.run(engine.advance("t1"))
        assert result["ok"]
        assert result["state"] == "wait_user"
        assert result["phase"] == "spec"
        result = asyncio.run(engine.confirm("t1", "spec"))
        assert result["ok"]
        assert result["state"] == "wait_user"
        assert result["phase"] == "design"
        task = engine.db.get_task("t1")
        assert task["phase"] == "design"
        assert task["status"] == "wait_user"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_spec_design_plan_full_flow():
    tmp = tempfile.mkdtemp(prefix="ede_se_")
    try:
        engine = _setup(tmp)
        engine.db.create_task("t2", "p1", "full flow")
        r = asyncio.run(engine.advance("t2"))
        assert r["state"] == "wait_user" and r["phase"] == "spec"
        r = asyncio.run(engine.confirm("t2", "spec"))
        assert r["state"] == "wait_user" and r["phase"] == "design"
        r = asyncio.run(engine.confirm("t2", "design"))
        assert r["state"] == "wait_user" and r["phase"] == "plan"
        r = asyncio.run(engine.confirm("t2", "plan"))
        assert r["state"] == "done" and r["phase"] == "code"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_confirm_wrong_stage_fails():
    tmp = tempfile.mkdtemp(prefix="ede_se_")
    try:
        engine = _setup(tmp)
        engine.db.create_task("t3", "p1", "wrong confirm")
        asyncio.run(engine.advance("t3"))
        result = asyncio.run(engine.confirm("t3", "design"))
        assert not result["ok"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_checkpoint_persists():
    tmp = tempfile.mkdtemp(prefix="ede_se_")
    try:
        engine = _setup(tmp)
        engine.db.create_task("t4", "p1", "persist test")
        asyncio.run(engine.advance("t4"))
        assert engine.db.table_count("checkpoint") >= 1
        asyncio.run(engine.confirm("t4", "spec"))
        assert engine.db.table_count("audit_log") >= 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_full_seven_phase_pipeline():
    tmp = tempfile.mkdtemp(prefix="ede_full2_")
    try:
        db_path = os.path.join(tmp, "state.db")
        db = Persistence(db_path)
        db.init_db()
        db.insert_project("p1", "full-test")
        gates = GateEngine()
        engine = StageEngine(db, gates, TrustConfig(tier="T0"))
        for phase in Phase:
            engine.register_stage(Stage(phase))
        engine.db.create_task("tx", "p1", "full pipeline")

        r = asyncio.run(engine.advance("tx"))
        assert r["state"] == "wait_user" and r["phase"] == "spec"
        r = asyncio.run(engine.confirm("tx", "spec"))
        assert r["phase"] == "design"
        r = asyncio.run(engine.confirm("tx", "design"))
        assert r["phase"] == "plan"
        r = asyncio.run(engine.confirm("tx", "plan"))
        assert r["phase"] == "code" and r["state"] == "done"

        for _ in range(5):
            task = engine.db.get_task("tx")
            if task["status"] == "done":
                r = asyncio.run(engine.advance("tx"))
                if r.get("state") == "terminal":
                    break

        assert engine.db.table_count("audit_log") >= 6
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
