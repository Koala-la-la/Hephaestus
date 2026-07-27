"""LLM Adapter — DeepSeek API integration with thinking budget and prefix cache.

Spec §5.4:
  - DeepSeekProvider wraps httpx for DeepSeek API
  - Thinking budget: off/low/medium/high/max
  - Prefix cache: stable constitution + conventions in system prompt
  - Phase-aware budget selection
"""

import asyncio
import os
import json
from typing import Protocol, Optional
from dataclasses import dataclass

import httpx

from ede.models import Phase


# ── Types ─────────────────────────────────────────────

@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResult:
    content: str
    thinking_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class LLMProvider(Protocol):
    """Minimal provider protocol — implement for DeepSeek, OpenAI, etc."""

    async def chat(self, messages: list[ChatMessage],
                   thinking_budget: str = "auto") -> ChatResult:
        ...

    def estimate_tokens(self, messages: list[ChatMessage]) -> int:
        ...


# ── Thinking budget mapping ───────────────────────────

PHASE_THINKING = {
    Phase.SPEC: "low",
    Phase.DESIGN: "low",
    Phase.PLAN: "medium",
    Phase.CODE: "high",
    Phase.TEST: "medium",
    Phase.REVIEW: "medium",
    Phase.MERGE: "off",
}

THINKING_BUDGETS = {
    "off": None,
    "low": 1024,
    "medium": 4096,
    "high": 8192,
    "max": 16384,
}


def thinking_for_phase(phase: Phase) -> str:
    """Return the recommended thinking budget for a pipeline phase."""
    return PHASE_THINKING.get(phase, "off")


# ── DeepSeek Provider ─────────────────────────────────

DEEPSEEK_SYSTEM_PROMPT = """You are EDE, the Engineering Discipline Enforcer.

## Hard Constraints (cannot be bypassed)
1. Never modify code without a confirmed spec and plan.
2. Every code change must include a structured change summary.
3. Group diffs by intent: interface / logic / test / refactor.
4. Label each change with risk: low / medium / high.
5. Never make irreversible decisions without user confirmation.
6. When uncertain about conventions, ASK rather than assume.
7. All outputs must include the change summary format.
8. Audit trail is immutable — bypasses are logged forever.

Output format for code changes:
```
## Change Summary
[2-3 sentences]

## Intent Groups
- interface: [files changed]
- logic: [files changed]
- test: [files changed]
- refactor: [files changed]

## Risk Assessment
- low: [items]
- medium: [items]
- high: [items — user MUST review]
```
"""

# Phase-specific rules (merged from prompt_layers)
PHASE_RULES = {
    Phase.SPEC: """## Phase: Requirements Clarification
Role: Guide the engineer through structured requirements discovery.
Rules:
- Ask focused questions, one topic at a time.
- Do NOT suggest technical solutions — focus on WHAT, not HOW.
- If requirements are ambiguous, flag them explicitly.
- Output: structured spec draft with acceptance criteria.""",

    Phase.DESIGN: """## Phase: System Design
Role: Collaborate on architecture decisions.
Rules:
- Present trade-offs explicitly: option A vs B with reasons and costs.
- Respect project constraints from context.yaml.
- Do NOT over-engineer — simplest working solution first.
- Output: design decisions with rationale.""",

    Phase.PLAN: """## Phase: Implementation Planning
Role: Produce a declarative change plan.
Rules:
- List every file to be changed, with operation type (create/modify/delete).
- Estimate risk per file (low/medium/high).
- Define rollback strategy.
- Output: structured plan table.""",

    Phase.CODE: """## Phase: Code Implementation
Role: Write code that passes all gates.
Rules:
- Follow project naming conventions from context.
- Every function must be single-responsibility.
- Handle errors explicitly — no bare except.
- Output: code changes + change summary + intent groups + risk labels.""",

    Phase.TEST: """## Phase: Testing
Role: Generate and run tests.
Rules:
- Test edge cases: null inputs, boundary values, error paths.
- Target coverage threshold from project config.
- Fix failures before proceeding.
- Output: test report + coverage summary.""",

    Phase.REVIEW: """## Phase: Code Review
Role: Multi-dimensional review of all changes.
Rules:
- Check spec compliance, robustness, and code standards.
- Report findings as: severity|file|message.
- Severities: error (must fix), warning (should fix), info (observation).""",

    Phase.MERGE: """## Phase: Merge
Role: Final gate before merging to main.
Rules:
- Verify all previous gates passed.
- Confirm audit trail is complete.
- Merge only with user confirmation (L4 decision).""",
}


class DeepSeekProvider:
    """DeepSeek API provider with thinking budget control."""

    DEFAULT_BASE_URL = "https://api.deepseek.com"

    def __init__(self, api_key: Optional[str] = None, model: str = "",
                 base_url: str = ""):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = model or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = base_url or os.environ.get(
            "DEEPSEEK_BASE_URL", DeepSeekProvider.DEFAULT_BASE_URL
        ).rstrip("/")

    async def chat(self, messages: list[ChatMessage],
                   thinking_budget: str = "auto") -> ChatResult:
        """Send a chat completion request to DeepSeek API.

        Retries only on rate-limit (429) / 5xx / transport errors; fails fast
        on other 4xx (e.g. 400 bad request, 401 unauthorized). Thinking budget
        is sent only for reasoner models (deepseek-reasoner); other models
        reject the ``thinking`` field with a 400, so it is omitted.

        Args:
            messages: conversation history
            thinking_budget: "off"|"low"|"medium"|"high"|"max"|"auto"

        Returns:
            ChatResult with content and token counts.
        """
        if not self.api_key:
            return ChatResult(content="[No API key configured. Set DEEPSEEK_API_KEY.]")

        payload = {
            "model": self.model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "stream": False,
        }

        # Thinking budget only applies to reasoner models (spec §5.4); other
        # models reject the field, so omit it rather than risk a 400.
        tokens = THINKING_BUDGETS.get(thinking_budget)
        if tokens is not None and "reasoner" in self.model.lower():
            payload["thinking"] = {"type": "enabled", "budget_tokens": tokens}

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        retryable = {429, 500, 502, 503, 504}

        last_error = "unknown"
        for attempt in range(5):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                if response.status_code in retryable:
                    last_error = f"HTTP {response.status_code}"
                    if attempt < 4:
                        await asyncio.sleep(min(1 << attempt, 30))
                    continue
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                usage = data.get("usage", {})
                return ChatResult(
                    content=choice["message"]["content"],
                    thinking_tokens=usage.get("completion_tokens_details", {}).get("thinking_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    model=data.get("model", self.model),
                )
            except httpx.HTTPStatusError as e:
                # Non-retryable 4xx — fail fast, do not retry.
                return ChatResult(content=f"[API Error: HTTP {e.response.status_code}]")
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_error = str(e)
                if attempt < 4:
                    await asyncio.sleep(min(1 << attempt, 30))
                continue
        return ChatResult(content=f"[API Error after 5 attempts: {last_error}]")

    def estimate_tokens(self, messages: list[ChatMessage]) -> int:
        """Rough token estimate: ~4 chars per token for Chinese/English mixed."""
        total = 0
        for m in messages:
            total += len(m.content) // 4
        return total

    # ── Convenience: build system prompt with context ──

    @staticmethod
    def build_system_prompt(context_yaml: str = "") -> str:
        """Build the system prompt prefix with stable constitution + project context."""
        prompt = DEEPSEEK_SYSTEM_PROMPT
        if context_yaml:
            prompt += f"\n\n## Project Context\n```yaml\n{context_yaml}\n```"
        return prompt
