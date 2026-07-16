"""Unit tests for LLM Adapter."""

import sys
sys.path.insert(0, r"C:\obsidian\KB\weiwei")

from ede.llm_adapter import (
    DeepSeekProvider, ChatMessage, ChatResult,
    thinking_for_phase, THINKING_BUDGETS, PHASE_THINKING,
    DEEPSEEK_SYSTEM_PROMPT,
)
from ede.models import Phase


def test_thinking_budget_mapping():
    """Each phase has a valid thinking budget."""
    for phase in Phase:
        budget = thinking_for_phase(phase)
        assert budget in THINKING_BUDGETS or budget == "auto"


def test_code_phase_high_budget():
    """Code phase gets high thinking budget."""
    assert thinking_for_phase(Phase.CODE) == "high"


def test_merge_phase_off_budget():
    """Merge phase gets no thinking (off)."""
    assert thinking_for_phase(Phase.MERGE) == "off"


def test_system_prompt_contains_constraints():
    """System prompt includes hard constraints."""
    assert "HARD CONSTRAINTS" in DEEPSEEK_SYSTEM_PROMPT
    assert "spec and plan" in DEEPSEEK_SYSTEM_PROMPT


def test_build_system_prompt_with_context():
    """System prompt builder injects project context."""
    ctx = "project:\n  type: web\n  frontend: react"
    prompt = DeepSeekProvider.build_system_prompt(ctx)
    assert "web" in prompt
    assert "react" in prompt
    assert "Project Context" in prompt


def test_estimate_tokens():
    """Token estimation is proportional to content length."""
    provider = DeepSeekProvider(api_key="test")
    msgs = [ChatMessage(role="user", content="Hello world " * 100)]
    est = provider.estimate_tokens(msgs)
    assert est > 0
    # ~1200 chars / 4 = ~300 tokens
    assert 200 < est < 500


def test_chat_without_api_key_returns_placeholder():
    """Chat without API key returns a placeholder message."""
    import asyncio
    provider = DeepSeekProvider(api_key="")
    msgs = [ChatMessage(role="user", content="Hi")]
    result = asyncio.run(provider.chat(msgs))
    assert "No API key" in result.content


def test_thinking_budget_token_values():
    """Thinking budget constants are correct."""
    assert THINKING_BUDGETS["off"] is None
    assert THINKING_BUDGETS["low"] == 1024
    assert THINKING_BUDGETS["medium"] == 4096
    assert THINKING_BUDGETS["high"] == 8192
