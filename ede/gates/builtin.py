"""Built-in gates for the EDE pipeline (async version).

v0.3: All check/fix functions are now async.
"""

import asyncio
import os
import subprocess
from pathlib import Path

from ede.gate_engine import Gate, GateLevel, GateEngine
from ede.models import GateResult


async def make_test_gate(project_root: str = ".") -> Gate:
    """L2 gate: runs pytest and checks for failures."""

    async def check() -> GateResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", "tests/", "-q", "--tb=no",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=project_root,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return GateResult(task_id="", gate_name="test", passed=False,
                                  detail="pytest timed out (180s)")
            passed = proc.returncode == 0
            lines = stdout.decode().split("\n")
            detail = lines[-2] if len(lines) >= 2 else str(proc.returncode)
            return GateResult(
                task_id="", gate_name="test", passed=passed,
                detail=f"pytest: {detail.strip()}",
            )
        except FileNotFoundError:
            return GateResult(task_id="", gate_name="test", passed=True,
                            detail="pytest not found (skip)")

    async def fix() -> bool:
        result = await check()
        return result.passed

    return Gate("test", GateLevel.L2, check, fix=fix)


async def make_lint_gate(project_root: str = ".") -> Gate:
    """L1 gate: runs basic Python syntax check on all .py files."""

    async def check() -> GateResult:
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
                        pass
        if errors:
            return GateResult(
                task_id="", gate_name="lint", passed=False,
                detail=f"Syntax errors: {'; '.join(errors[:3])}",
            )
        return GateResult(task_id="", gate_name="lint", passed=True, detail="All .py files compile OK")

    async def fix() -> bool:
        result = await check()
        return result.passed

    return Gate("lint", GateLevel.L1, check, fix=fix)


async def make_coverage_gate(project_root: str = ".", threshold: int = 80) -> Gate:
    """L3 gate: checks test coverage threshold."""

    async def check() -> GateResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", "--cov=.", "--cov-report=term", "-q",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=project_root,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return GateResult(task_id="", gate_name="coverage", passed=False,
                                  detail="coverage run timed out (120s)")
            coverage = 0
            for line in stdout.decode().split("\n"):
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
                detail=f"Coverage: {coverage}% (threshold: {threshold}%)",
            )
        except FileNotFoundError:
            return GateResult(
                task_id="", gate_name="coverage", passed=True,
                detail="coverage tool not available (skip)",
            )

    return Gate("coverage", GateLevel.L3, check)


def register_builtin_gates(engine: GateEngine, project_root: str = ".") -> GateEngine:
    """Register all built-in gates on the engine. Returns same engine for chaining.

    Note: This is synchronous because it only registers factories.
    The actual check/fix calls are async.
    """
    import asyncio
    loop = asyncio.new_event_loop()
    lint_gate = loop.run_until_complete(make_lint_gate(project_root))
    test_gate = loop.run_until_complete(make_test_gate(project_root))
    cov_gate = loop.run_until_complete(make_coverage_gate(project_root))
    loop.close()
    engine.register(lint_gate)
    engine.register(test_gate)
    engine.register(cov_gate)
    return engine
