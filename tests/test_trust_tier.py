"""Unit tests for Trust Tier — T0 through T3 behavior."""

import sys
import os
import tempfile
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ede.context_engine import TrustConfig
from ede.stage_engine import StageEngine, Stage
from ede.gate_engine import GateEngine, Gate, GateLevel
from ede.persistence import Persistence
from ede.models import Phase, TaskStatus, GateResult


def _setup_engine(tmpdir: str, tier: str) -> StageEngine:
    db = Persistence(os.path.join(tmpdir, "state.db"))
    db.init_db()
    db.insert_project("p1", "test")
    gates = GateEngine()
    engine = StageEngine(db, gates, TrustConfig(tier=tier))
    for phase in Phase:
        engine.register_stage(Stage(phase))
    return engine


# ── TrustConfig unit tests ────────────────────────────

def test_t0_blocks_human_checkpoint():
    tc = TrustConfig(tier="T0")
    assert tc.should_block_human_checkpoint("spec")
    assert tc.should_block_human_checkpoint("design")
    assert tc.should_block_human_checkpoint("plan")


def test_t1_passes_human_checkpoint():
    tc = TrustConfig(tier="T1")
    assert not tc.should_block_human_checkpoint("spec")
    assert not tc.should_block_human_checkpoint("plan")


def test_t2_passes_checkpoint_and_l3():
    tc = TrustConfig(tier="T2")
    assert not tc.should_block_human_checkpoint("spec")
    assert not tc.should_block_on_l3_failure("code")


def test_t3_full_auto():
    tc = TrustConfig(tier="T3")
    assert not tc.should_block_human_checkpoint("spec")
    assert not tc.should_block_on_l3_failure("code")


def test_override_phase():
    tc = TrustConfig(tier="T2", overrides={"merge": "T0"})
    assert tc.effective_tier("code") == "T2"
    assert tc.effective_tier("merge") == "T0"
    assert tc.should_block_human_checkpoint("merge")
    assert not tc.should_block_human_checkpoint("code")


def test_invalid_tier_defaults_to_t1():
    tc = TrustConfig(tier="INVALID")
    assert tc.tier == "T1"


def test_max_retries_by_tier():
    tc0 = TrustConfig(tier="T0")
    tc2 = TrustConfig(tier="T2")
    tc3 = TrustConfig(tier="T3")
    assert tc0.max_auto_retries("code", 1) == 2  # T0 L1
    assert tc0.max_auto_retries("code", 2) == 1  # T0 L2
    assert tc0.max_auto_retries("code", 3) == 0  # T0 L3
    assert tc2.max_auto_retries("code", 1) == 3  # T2 L1
    assert tc2.max_auto_retries("code", 3) == 1  # T2 L3 gets 1 retry
    assert tc3.max_auto_retries("code", 2) == 3  # T3 L2


# ── StageEngine integration tests ─────────────────────

def test_t1_skips_spec_checkpoint():
    tmp = tempfile.mkdtemp(prefix="ede_tt_")
    try:
        engine = _setup_engine(tmp, "T1")
        engine.db.create_task("t1", "p1", "t1 test")
        r = engine.advance("t1")
        assert r["state"] == "done"  # T1 auto-passes spec checkpoint
        assert r["phase"] == "spec"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_t0_blocks_spec_checkpoint():
    tmp = tempfile.mkdtemp(prefix="ede_tt_")
    try:
        engine = _setup_engine(tmp, "T0")
        engine.db.create_task("t2", "p1", "t2 test")
        r = engine.advance("t2")
        assert r["state"] == "wait_user"  # T0 blocks
        assert r["phase"] == "spec"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_t2_auto_flows_through_all_checkpoints():
    tmp = tempfile.mkdtemp(prefix="ede_tt_")
    try:
        engine = _setup_engine(tmp, "T2")
        engine.db.create_task("t3", "p1", "full flow")

        r = engine.advance("t3")
        # T2: all checkpoints auto-pass, should reach code or beyond
        phases = {r["phase"]}
        # Keep advancing until terminal or stuck
        for _ in range(10):
            task = engine.db.get_task("t3")
            if task["status"] == "done":
                r = engine.advance("t3")
                if r.get("state") == "terminal":
                    break
                phases.add(r.get("phase", "?"))

        # Should have traversed multiple phases without human intervention
        assert len(phases) >= 3
        # Verify audit log recorded auto_checkpoint
        logs = engine.db.get_audit_logs("t3")
        auto_logs = [l for l in logs if "auto_checkpoint" in l.get("action", "")]
        assert len(auto_logs) >= 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_t1_override_merge_to_t0():
    tmp = tempfile.mkdtemp(prefix="ede_tt_")
    try:
        db = Persistence(os.path.join(tmp, "state.db"))
        db.init_db()
        db.insert_project("p1", "test")
        gates = GateEngine()
        tc = TrustConfig(tier="T1", overrides={"merge": "T0"})
        engine = StageEngine(db, gates, tc)
        for phase in Phase:
            engine.register_stage(Stage(phase))
        engine.db.create_task("t4", "p1", "override test")

        assert engine.trust.effective_tier("code") == "T1"
        assert engine.trust.effective_tier("merge") == "T0"
        assert engine.trust.should_block_human_checkpoint("merge")
        assert not engine.trust.should_block_human_checkpoint("code")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
