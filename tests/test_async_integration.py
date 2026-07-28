"""Integration tests for the async pipeline (v0.3 regression guards).

Covers:
  - P0: an async stage run_fn that awaits an async LLM call must work inside
    asyncio.run(advance()). The old sync ``loop.run_until_complete`` pattern
    raised ``RuntimeError: This event loop is already running`` once a real
    GLM_API_KEY was configured (the unit suite never caught it because
    run_fn early-returns when no key is set).
  - P1: gate check results are persisted to the ``gate_result`` table (spec §5.2).
"""

import asyncio
import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ede.stage_engine import StageEngine, Stage
from ede.gate_engine import GateEngine, Gate, GateLevel
from ede.persistence import Persistence
from ede.context_engine import TrustConfig
from ede.llm_adapter import ChatResult
from ede.models import Phase, GateResult
from ede.change_visibility import parse_change_summary, parse_change_entries


CANNED_LLM_OUTPUT = """## Change Summary
Added a JWT auth helper in auth.py.

## Intent Groups
- interface: auth.py
- logic: none
- test: none
- refactor: none

## Risk Assessment
- low: none
- medium: none
- high: none
"""


class _FakeLLM:
    """Async LLM stub implementing the chat() protocol used by the CLI run_fn."""

    def __init__(self):
        self.calls = 0

    async def chat(self, messages, thinking_budget="auto"):
        self.calls += 1
        return ChatResult(content=CANNED_LLM_OUTPUT, output_tokens=42)


def _setup_engine(tmpdir: str, tier: str = "T1") -> StageEngine:
    db = Persistence(os.path.join(tmpdir, "state.db"))
    db.init_db()
    db.insert_project("p1", "test")
    engine = StageEngine(db, GateEngine(), TrustConfig(tier=tier))
    for ph in Phase:
        engine.register_stage(Stage(ph))
    return engine


def test_async_run_fn_awaits_llm_inside_pipeline():
    """P0 guard: async run_fn + await LLM must not deadlock the running loop.

    Under the old sync ``stage.run_fn(...)`` call + ``loop.run_until_complete``,
    this raised ``RuntimeError: This event loop is already running``. With the
    fix (await on an async run_fn) the LLM is awaited exactly once and the
    change log is persisted.
    """
    tmp = tempfile.mkdtemp(prefix="ede_async_")
    try:
        engine = _setup_engine(tmp)
        llm = _FakeLLM()

        async def code_run(task_id, phase):
            result = await llm.chat([])
            if result.content and "Change Summary" in result.content:
                ch = parse_change_summary(result.content)
                ch.task_id = task_id
                engine.db.insert_change_log(ch)
                for entry in parse_change_entries(result.content, ch.change_id):
                    engine.db.insert_change_entry(entry)

        engine._stages[Phase.CODE] = Stage(
            Phase.CODE, prerequisites=[], gates=[], run_fn=code_run
        )
        # Start directly at CODE so a single advance() exercises the run_fn.
        engine.db.create_task("t1", "p1", "async run_fn test", start_phase="code")

        asyncio.run(engine.advance("t1"))

        assert llm.calls == 1, f"LLM should be awaited once at CODE, got {llm.calls}"
        logs = engine.db.get_change_logs("t1")
        assert len(logs) == 1, f"ChangeLog should be persisted, got {len(logs)}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_gate_results_are_persisted():
    """P1 guard: gate results are written to gate_result (spec §5.2)."""
    tmp = tempfile.mkdtemp(prefix="ede_gr_")
    try:
        engine = _setup_engine(tmp)

        async def _pass_check():
            return GateResult(task_id="", gate_name="custom", passed=True, detail="ok")

        engine.gates.register(Gate("custom", GateLevel.L1, _pass_check))
        engine._stages[Phase.CODE] = Stage(Phase.CODE, gates=["custom"])
        engine.db.create_task("t2", "p1", "gate persist test", start_phase="code")

        asyncio.run(engine.advance("t2"))

        assert engine.db.table_count("gate_result") >= 1, "gate_result not persisted"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
