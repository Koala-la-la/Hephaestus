"""Unit tests for Self-Refinement Engine."""

import sys, os, tempfile, shutil
sys.path.insert(0, r"C:\obsidian\KB\weiwei")

from ede.self_refinement import SelfRefinement


def test_analyze_empty_logs():
    """Empty audit logs produce no suggestions."""
    sr = SelfRefinement("/tmp")
    suggestions = sr.analyze([])
    assert suggestions == []


def test_analyze_blocked_gate():
    """Blocked gate produces a constraint suggestion."""
    sr = SelfRefinement("/tmp")
    logs = [{"action": "gates_failed", "detail": "lint check failed"}]
    suggestions = sr.analyze(logs)
    assert len(suggestions) >= 1
    assert suggestions[0]["type"] == "constraint"
    assert "lint" in suggestions[0]["content"]


def test_analyze_l3_blocked():
    """L3 blocked produces a history suggestion."""
    sr = SelfRefinement("/tmp")
    logs = [{"action": "l3_blocked", "detail": "coverage threshold not met"}]
    suggestions = sr.analyze(logs)
    assert len(suggestions) >= 1
    assert suggestions[0]["type"] == "history"


def test_deduplicate_suggestions():
    """Duplicate log entries produce only one suggestion."""
    sr = SelfRefinement("/tmp")
    logs = [
        {"action": "gates_failed", "detail": "lint"},
        {"action": "gates_failed", "detail": "lint"},
    ]
    suggestions = sr.analyze(logs)
    assert len(suggestions) == 1


def test_apply_writes_context_yaml():
    """Apply writes suggestions to context.yaml."""
    tmp = tempfile.mkdtemp(prefix="ede_sr_")
    try:
        ede_dir = os.path.join(tmp, ".ede")
        os.makedirs(ede_dir)
        ctx_path = os.path.join(ede_dir, "context.yaml")
        with open(ctx_path, "w", encoding="utf-8") as f:
            f.write("constraints: []\nhistory: []\n")

        sr = SelfRefinement(tmp)
        suggestions = [{"type": "constraint", "content": "use soft delete"}]
        result = sr.apply(suggestions)
        assert result["updated"] == 1

        content = open(ctx_path, encoding="utf-8").read()
        assert "soft delete" in content
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_summary_formatting():
    """Summary output includes suggestion count."""
    sr = SelfRefinement("/tmp")
    suggestions = [{"type": "constraint", "content": "test pattern"}]
    summary = sr.get_suggestions_summary(suggestions)
    assert "constraint" in summary
    assert "test pattern" in summary
