"""Unit tests for Context Engine."""

import sys, os, tempfile, shutil
sys.path.insert(0, r"C:\obsidian\KB\weiwei")

from ede.context_engine import ContextEngine, ProjectContext


def test_default_context():
    """Context engine returns defaults when no context.yaml exists."""
    engine = ContextEngine("/nonexistent")
    ctx = engine.load()
    assert ctx.naming == "snake_case"
    assert ctx.api_style == "rest"
    assert ctx.project_type == ""


def test_load_context_from_file():
    """Context engine parses a valid context.yaml."""
    tmp = tempfile.mkdtemp(prefix="ede_ctx_")
    try:
        ede_dir = os.path.join(tmp, ".ede")
        os.makedirs(ede_dir)
        with open(os.path.join(ede_dir, "context.yaml"), "w", encoding="utf-8") as f:
            f.write("project:\n  type: web_fullstack\n  frontend: react\n  backend: python\n  database: postgresql\nconventions:\n  naming: snake_case\n  api_style: rest\nconstraints:\n  - soft delete only\nhistory:\n  - past mistake 1\n")

        engine = ContextEngine(tmp)
        ctx = engine.load()
        assert ctx.project_type == "web_fullstack"
        assert ctx.frontend == "react"
        assert ctx.backend == "python"
        assert ctx.database == "postgresql"
        assert len(ctx.constraints) == 1
        assert ctx.constraints[0] == "soft delete only"
        assert len(ctx.history) == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_to_prompt_prefix():
    """ProjectContext generates a readable prompt prefix."""
    ctx = ProjectContext(
        project_type="web",
        frontend="react",
        backend="fastapi",
        constraints=["use soft delete"],
    )
    prefix = ctx.to_prompt_prefix()
    assert "web" in prefix
    assert "react" in prefix
    assert "fastapi" in prefix
    assert "soft delete" in prefix


def test_resolve_returns_string():
    """ContextEngine.resolve() returns a non-empty string."""
    tmp = tempfile.mkdtemp(prefix="ede_ctx_")
    try:
        ede_dir = os.path.join(tmp, ".ede")
        os.makedirs(ede_dir)
        with open(os.path.join(ede_dir, "context.yaml"), "w", encoding="utf-8") as f:
            f.write("project:\n  type: cli_tool\n")

        engine = ContextEngine(tmp)
        result = engine.resolve()
        assert "cli_tool" in result
        assert len(result) > 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
