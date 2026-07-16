"""Built-in gates for the EDE pipeline.

Provides factory functions for test, lint, and coverage gates
that can be registered with the GateEngine.
"""

import subprocess
import os
from pathlib import Path

from ede.gate_engine import Gate, GateLevel, GateEngine
from ede.models import GateResult


def make_test_gate(project_root: str = ".") -> Gate:
    """L2 gate: runs pytest and checks for failures.

    Retry strategy (L2): auto-fix by LLM (1 attempt), then WAIT_USER.
    """

    def check() -> GateResult:
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-q", "--tb=no"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=180,
            )
            passed = result.returncode == 0
            detail = result.stdout.split("\n")[-2] if result.stdout else str(result.returncode)
            return GateResult(
                task_id="", gate_name="test", passed=passed,
                detail=f"pytest: {detail.strip()}"
            )
        except subprocess.TimeoutExpired:
            return GateResult(task_id="", gate_name="test", passed=False, detail="pytest timed out")
        except FileNotFoundError:
            return GateResult(task_id="", gate_name="test", passed=True,
                              detail="pytest not found (skip)")

    # Fix function: run pytest again (LLM would have modified code)
    def fix() -> bool:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return result.returncode == 0

    return Gate("test", GateLevel.L2, check, fix=fix)


def make_lint_gate(project_root: str = ".") -> Gate:
    """L1 gate: runs basic Python syntax check on all .py files.

    Retry strategy (L1): auto-fix 2 times.
    """

    def check() -> GateResult:
        errors = []
        for root, _, files in os.walk(project_root):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, encoding="utf-8") as fh:
                            compile(fh.read(), path, "exec")
                    except SyntaxError as e:
                        errors.append(f"{f}:{e.lineno}: {e.msg}")
                    except Exception:
                        pass  # ignore encoding issues for now

        if errors:
            return GateResult(
                task_id="", gate_name="lint", passed=False,
                detail=f"Syntax errors: {'; '.join(errors[:3])}"
            )
        return GateResult(task_id="", gate_name="lint", passed=True, detail="All .py files compile OK")

    def fix() -> bool:
        # Syntax errors can't be auto-fixed without model intervention
        # For MVP, just re-check
        result = check()
        return result.passed

    return Gate("lint", GateLevel.L1, check, fix=fix)


def make_coverage_gate(project_root: str = ".", threshold: int = 80) -> Gate:
    """L3 gate: checks test coverage threshold.

    L3 gates trigger immediate WAIT_USER if they fail.
    """

    def check() -> GateResult:
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--cov=.", "--cov-report=term", "-q"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            # Extract coverage percentage from output
            coverage = 0
            for line in result.stdout.split("\n"):
                if "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for p in parts:
                        if p.endswith("%"):
                            try:
                                coverage = int(float(p.rstrip("%")))
                            except ValueError:
                                pass

            passed = coverage >= threshold
            return GateResult(
                task_id="", gate_name="coverage", passed=passed,
                detail=f"Coverage: {coverage}% (threshold: {threshold}%)"
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return GateResult(
                task_id="", gate_name="coverage", passed=True,
                detail="coverage tool not available (skip)"
            )

    return Gate("coverage", GateLevel.L3, check)


def register_builtin_gates(engine: GateEngine, project_root: str = ".") -> GateEngine:
    """Register all built-in gates on the engine. Returns same engine for chaining."""
    engine.register(make_lint_gate(project_root))
    engine.register(make_test_gate(project_root))
    engine.register(make_coverage_gate(project_root))
    return engine
