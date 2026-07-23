"""Unit tests for builtin gates (async)."""

import sys, os, tempfile, shutil, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ede.gates.builtin import (
    make_lint_gate, make_test_gate, make_coverage_gate, register_builtin_gates,
)
from ede.gate_engine import GateEngine


def test_lint_gate_passes_on_clean_code():
    """Lint gate passes on a valid Python file."""
    tmp = tempfile.mkdtemp(prefix="ede_gate_")
    try:
        with open(os.path.join(tmp, "ok.py"), "w", encoding="utf-8") as f:
            f.write("def foo(): return 42\n")
        gate = asyncio.run(make_lint_gate(tmp))
        result = asyncio.run(gate.check())
        assert result.passed
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_lint_gate_fails_on_syntax_error():
    """Lint gate catches syntax errors."""
    tmp = tempfile.mkdtemp(prefix="ede_gate_")
    try:
        with open(os.path.join(tmp, "bad.py"), "w", encoding="utf-8") as f:
            f.write("def foo(:\n    return 42\n")
        gate = asyncio.run(make_lint_gate(tmp))
        result = asyncio.run(gate.check())
        assert not result.passed
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_test_gate_runs_on_this_project():
    """Test gate runs pytest on the EDE project."""
    gate = asyncio.run(make_test_gate(r"C:\obsidian\KB\weiwei"))
    result = asyncio.run(gate.check())
    assert result.detail != "", "Gate returned empty detail"


def test_register_builtin_gates():
    """All 3 builtin gates are registered."""
    engine = GateEngine()
    register_builtin_gates(engine, r"C:\obsidian\KB\weiwei")
    assert len(engine._gates) == 3
    assert "lint" in engine._gates
    assert "test" in engine._gates
    assert "coverage" in engine._gates
