"""Unit tests for Reviewer Orchestrator."""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ede.reviewer import (
    Reviewer, ReviewFinding, ReviewReport, ReviewerOrchestrator,
)
from ede.llm_adapter import GLMProvider, ChatMessage, ChatResult


def _mock_provider():
    """Create a provider that returns fake responses."""
    class MockProvider:
        call_count = 0
        async def chat(self, messages, thinking_budget="auto"):
            MockProvider.call_count += 1
            content = ""
            if MockProvider.call_count == 1:
                content = "warning|utils.py|Missing input validation"
            elif MockProvider.call_count == 2:
                content = "error|auth.py|Unhandled exception in login"
            else:
                content = "info|style.py|Function name should be snake_case"
            return ChatResult(content=content, output_tokens=10)
    return MockProvider()


def test_review_report_markdown():
    """ReviewReport generates readable markdown."""
    report = ReviewReport(task_id="t1")
    report.findings.append(ReviewFinding(
        reviewer="standards", dimension="Code Standards",
        severity="warning", file="a.py", message="Use snake_case"
    ))
    report.total_warnings = 1
    report.summary = "1 warning"
    md = report.to_markdown()
    assert "Review Report" in md
    assert "t1" in md
    assert "Code Standards" in md
    assert "snake_case" in md


def test_reviewer_definition():
    """Reviewer dataclass holds all required fields."""
    r = Reviewer(
        name="test", dimension="Test Dim",
        system_prompt="be thorough",
        review_prompt_template="Review: {diff}"
    )
    assert r.name == "test"
    assert "{diff}" in r.review_prompt_template


def test_orchestrator_has_defaults():
    """Orchestrator registers 3 default reviewers on init."""
    provider = GLMProvider(api_key="mock")
    orch = ReviewerOrchestrator(provider)
    assert len(orch._reviewers) == 3
    names = [r.name for r in orch._reviewers]
    assert "spec-compliance" in names
    assert "robustness" in names
    assert "standards" in names


def test_parse_pipe_format():
    """_parse_findings handles pipe-separated output."""
    provider = GLMProvider(api_key="mock")
    orch = ReviewerOrchestrator(provider)
    reviewer = orch._reviewers[0]
    content = "warning|file.py|Missing docstring\nerror|main.py|Unhandled error"
    findings = orch._parse_findings(reviewer, content)
    assert len(findings) == 2
    assert findings[0].severity == "warning"
    assert findings[0].file == "file.py"
    assert findings[1].severity == "error"


def test_parse_plain_text():
    """_parse_findings catches unstructured warning lines."""
    provider = GLMProvider(api_key="mock")
    orch = ReviewerOrchestrator(provider)
    reviewer = orch._reviewers[0]
    content = "This code has an issue with error handling"
    findings = orch._parse_findings(reviewer, content)
    assert len(findings) >= 1
    assert findings[0].severity == "warning"


def test_add_custom_reviewer():
    """Custom reviewers can be registered."""
    provider = GLMProvider(api_key="mock")
    orch = ReviewerOrchestrator(provider)
    orch.add_reviewer(Reviewer(name="custom", dimension="Custom", system_prompt="", review_prompt_template=""))
    assert len(orch._reviewers) == 4
