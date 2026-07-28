"""Tests for new features: --start-at, ChangeEntry CRUD, accuracy review."""

import sys, os, tempfile, shutil, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ede.persistence import Persistence
from ede.models import (
    ChangeEntry, DisagreementEvidence, IntentGroup, RiskLabel, Phase,
)


def test_create_task_start_at_code():
    """Task created with start_phase='code' starts at CODE/PENDING."""
    tmp = tempfile.mkdtemp(prefix="ede_new_")
    try:
        db = Persistence(str(Path(tmp) / "state.db"))
        db.init_db()
        db.insert_project("p1", "test")
        db.create_task("t-code", "p1", "fix", start_phase="code")
        task = db.get_task("t-code")
        assert task["phase"] == "code"
        assert task["status"] == "pending"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_create_task_bad_start_phase_falls_back():
    """Invalid start_phase falls back to spec."""
    tmp = tempfile.mkdtemp(prefix="ede_new_")
    try:
        db = Persistence(str(Path(tmp) / "state.db"))
        db.init_db()
        db.insert_project("p1", "test")
        db.create_task("t-bad", "p1", "test", start_phase="nonexistent")
        task = db.get_task("t-bad")
        assert task["phase"] == "spec"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_change_entry_insert_and_get():
    """ChangeEntry round-trip: insert + get."""
    tmp = tempfile.mkdtemp(prefix="ede_new_")
    try:
        db = Persistence(str(Path(tmp) / "state.db"))
        db.init_db()
        db.insert_project("p1", "test")

        entry = ChangeEntry(
            entry_id="e-001", change_id="c-001",
            intent_group=IntentGroup.LOGIC,
            agent_risk_label=RiskLabel.LOW,
            effective_risk_label=RiskLabel.LOW,
            file_path="main.py", summary="auth logic",
        )
        db.insert_change_entry(entry)
        entries = db.get_change_entries("c-001")
        assert len(entries) == 1
        assert entries[0]["entry_id"] == "e-001"
        assert entries[0]["agent_risk_label"] == "low"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_change_entry_accuracy_upgrade():
    """low + inaccurate → effective_risk upgraded to medium."""
    entry = ChangeEntry(
        entry_id="e-002", change_id="c-002",
        intent_group=IntentGroup.LOGIC,
        agent_risk_label=RiskLabel.LOW,
        effective_risk_label=RiskLabel.LOW,
    )
    entry.upgrade_if_inaccurate("inaccurate")
    assert entry.accuracy_score == "inaccurate"
    assert entry.effective_risk_label == RiskLabel.MEDIUM


def test_change_entry_accuracy_partial():
    """partial does NOT upgrade risk."""
    entry = ChangeEntry(
        entry_id="e-003", change_id="c-003",
        intent_group=IntentGroup.INTERFACE,
        agent_risk_label=RiskLabel.MEDIUM,
        effective_risk_label=RiskLabel.MEDIUM,
    )
    entry.upgrade_if_inaccurate("partial")
    assert entry.accuracy_score == "partial"
    assert entry.effective_risk_label == RiskLabel.MEDIUM


def test_change_entry_high_stays_high():
    """HIGH risk cannot be upgraded further."""
    entry = ChangeEntry(
        entry_id="e-004", change_id="c-004",
        agent_risk_label=RiskLabel.HIGH,
        effective_risk_label=RiskLabel.HIGH,
    )
    entry.upgrade_if_inaccurate("inaccurate")
    assert entry.effective_risk_label == RiskLabel.HIGH


def test_disagreement_evidence_crud():
    """DisagreementEvidence insert + get round-trip."""
    tmp = tempfile.mkdtemp(prefix="ede_new_")
    try:
        db = Persistence(str(Path(tmp) / "state.db"))
        db.init_db()
        db.insert_project("p1", "test")

        ev = DisagreementEvidence(
            reviewer="accuracy", severity="error",
            file_path="payment.py", line_number=45,
            agent_claim="logging only, low risk",
            reviewer_reason="removed @Transactional",
            diff_quote="- @Transactional(propagation=REQUIRED)",
        )
        db.insert_disagreement_evidence("e-001", ev)
        records = db.get_disagreement_evidences("e-001")
        assert len(records) == 1
        assert records[0]["line_number"] == 45
        assert "@Transactional" in records[0]["diff_quote"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_accuracy_reviewer_parse_drops_bad_findings():
    """Findings without line_number or diff_quote are dropped."""
    from ede.reviewer import ReviewerOrchestrator, Reviewer
    from ede.llm_adapter import GLMProvider

    orch = ReviewerOrchestrator(GLMProvider(api_key="mock"))
    reviewer = Reviewer(name="accuracy", dimension="Accuracy",
                        system_prompt="", review_prompt_template="")

    # Lines 1+3 valid (digit line_number + non-empty diff_quote); lines 2+4 dropped
    content = (
        "error|auth.py|45|low risk|removed auth|  - @Transactional\n"
        "error|main.py||missing claim|no evidence|\n"
        "warning|utils.py|10|cosmetic|renamed var|  def foo()\n"
        "info||-|accurate||\n"
    )
    findings = orch._parse_findings_with_citations(reviewer, content)
    assert len(findings) == 2
    assert findings[0].file == "auth.py"
    assert findings[0].line == "45"
    assert findings[1].file == "utils.py"


def test_parse_change_entries_multi_file():
    """parse_change_entries splits LLM output into per-file entries."""
    from ede.change_visibility import parse_change_entries

    llm_output = """## Change Summary
Refactored auth and added tests.

## Intent Groups
- interface: auth.py
- logic: user.py, session.py
- test: test_auth.py
- refactor: none

## Risk Assessment
- low: test additions, refactor
- medium: auth interface change
- high: session logic change
"""
    entries = parse_change_entries(llm_output, "c-test")
    assert len(entries) >= 3
    files = {e.file_path for e in entries}
    assert "auth.py" in files
    # parser treats comma-separated files as one entry string
    assert "user.py, session.py" in files or "user.py" in files


def test_audit_integrity_chain():
    """Audit log entries form a SHA256 chain; tampering is detectable."""
    tmp = tempfile.mkdtemp(prefix="ede_new_")
    try:
        db = Persistence(str(Path(tmp) / "state.db"))
        db.init_db()
        db.insert_project("p1", "test")
        db.create_task("t-ai", "p1", "test")

        db.write_audit("t-ai", "step1", "first action")
        db.write_audit("t-ai", "step2", "second action")

        result = db.verify_audit_integrity("t-ai")
        assert result["valid"], f"Chain should be valid, got: {result}"

        # Corrupt a hash
        import sqlite3
        conn = sqlite3.connect(str(Path(tmp) / "state.db"))
        conn.execute(
            "UPDATE audit_log SET integrity_hash='deadbeef' WHERE task_id='t-ai' AND action='step1'"
        )
        conn.commit()
        conn.close()

        result = db.verify_audit_integrity("t-ai")
        assert not result["valid"], "Chain should be broken after tampering"
        assert result["broken_at"] is not None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
