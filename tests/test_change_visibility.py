"""Unit tests for Change Visibility Engine."""

import sys
sys.path.insert(0, r"C:\obsidian\KB\weiwei")

from ede.change_visibility import (
    parse_change_summary, build_change_summary_prompt,
    _extract_section, _extract_intent_groups, _extract_risk_label,
)
from ede.models import IntentGroup, RiskLabel, ChangeLog


SAMPLE_OUTPUT = """## Change Summary
Fixed login bug by adding rate limiting. Updated User model to include last_login field.
Added tests for auth flow.

## Intent Groups
- interface: auth.py (added rate_limit decorator)
- logic: user.py (added last_login tracking)
- test: test_auth.py (new tests for rate limiting)
- refactor: none

## Risk Assessment
- low: test additions
- medium: rate limiting logic affects login flow
- high: user model schema change
"""

SAMPLE_LOW_RISK = """## Change Summary
Added docstrings to utility functions.

## Intent Groups
- interface: none
- logic: none
- test: none
- refactor: utils.py (added docstrings)

## Risk Assessment
- low: cosmetic changes only
- medium: none
- high: none
"""


def test_parse_summary_extracts_fields():
    cl = parse_change_summary(SAMPLE_OUTPUT)
    assert cl.summary != ""
    assert "rate limiting" in cl.summary
    assert cl.intent_group == IntentGroup.LOGIC
    assert cl.risk_label == RiskLabel.HIGH
    assert cl.diff_hash != ""


def test_extract_section_header():
    s = _extract_section(SAMPLE_OUTPUT, "Change Summary")
    assert "Fixed login bug" in s


def test_intent_logic_wins_over_interface():
    intent = _extract_intent_groups(SAMPLE_OUTPUT)
    assert intent == IntentGroup.LOGIC


def test_risk_high_wins():
    risk = _extract_risk_label(SAMPLE_OUTPUT)
    assert risk == RiskLabel.HIGH


def test_low_risk_when_no_items():
    risk = _extract_risk_label(SAMPLE_LOW_RISK)
    assert risk == RiskLabel.LOW


def test_build_prompt_includes_task():
    prompt = build_change_summary_prompt("Fix auth bug")
    assert "Fix auth bug" in prompt
    assert "Change Summary" in prompt


def test_empty_output_returns_defaults():
    cl = parse_change_summary("")
    assert cl.summary == ""
    assert cl.intent_group == IntentGroup.LOGIC
    assert cl.risk_label == RiskLabel.LOW
