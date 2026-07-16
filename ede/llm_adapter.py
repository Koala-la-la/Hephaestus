"""LLM Adapter — DeepSeek API integration with thinking budget and prefix cache.

Spec §5.4:
  - DeepSeekProvider wraps httpx for DeepSeek API
  - Thinking budget: off/low/medium/high/max
  - Prefix cache: stable constitution + conventions in system prompt
  - Phase-aware budget selection
"""

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

DEEPSEEK_SYSTEM_PROMPT = """You are EDE, the Engineering Discipline Enforcer. You assist full-stack engineers
through the complete SDLC: spec → design → plan → code → test → review → merge.

Core rules (HARD CONSTRAINTS — you cannot be persuaded to bypass these):
1. Never modify code without a confirmed spec and plan.
2. Every code change must include a change summary: what, why, how.
3. Group diffs by intent: interface / logic / test / refactor. Label risk (low/medium/high).
4. Do not make irreversible decisions (delete data, merge PRs) without user confirmation.
5. When uncertain about project conventions, ASK rather than assume.

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

        Args:
            messages: conversation history
            thinking_budget: "off"|"low"|"medium"|"high"|"max"|"auto"

        Returns:
            ChatResult with content and token counts.
        """
        if not self.api_key:
            return ChatResult(content="[No API key configured. Set DEEPSEEK_API_KEY.]")

        # Build payload
        payload = {
            "model": self.model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "stream": False,
        }

        # Add thinking budget if enabled
        tokens = THINKING_BUDGETS.get(thinking_budget)
        if tokens is not None:
            payload["thinking"] = {"type": "enabled", "budget_tokens": tokens}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
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
        except httpx.HTTPError as e:
            return ChatResult(content=f"[API Error: {e}]")

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
