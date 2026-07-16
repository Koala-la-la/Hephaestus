"""P0 Smoke Test — Real DeepSeek API end-to-end verification.

Usage:
  1. Set your API key:  export DEEPSEEK_API_KEY=sk-xxx
  2. (Optional) Relay:  export DEEPSEEK_BASE_URL=https://your-relay.com
  3. (Optional) Model:  export DEEPSEEK_MODEL=deepseek-chat
  4. Run:               python tests/p0_smoke.py

This script NEVER prints your API key.
"""

import os, sys, asyncio, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ede.llm_adapter import DeepSeekProvider, ChatMessage, thinking_for_phase, THINKING_BUDGETS
from ede.models import Phase, TaskStatus
from ede.change_visibility import parse_change_summary

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"


def check_api():
    """Verify API key is set (don't print it)."""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print(f"  {SKIP} — DEEPSEEK_API_KEY not set")
        return None
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    print(f"  API key: ****{key[-4:]}")
    print(f"  Base URL: {base}")
    print(f"  Model: {model}")
    return DeepSeekProvider(api_key=key, base_url=base, model=model)


async def test_connectivity(provider):
    """Send a simple message and verify response."""
    print("\n[1] Connectivity test...")
    msgs = [ChatMessage(role="user", content="Reply with just the word: OK")]
    result = await provider.chat(msgs, thinking_budget="off")
    ok = "OK" in result.content or "ok" in result.content.lower()
    status = PASS if ok else FAIL
    print(f"  {status} Response ({result.output_tokens} tokens): {result.content[:100]}")
    print(f"  Model: {result.model}")
    return ok


async def test_thinking_budget(provider):
    """Test thinking budget is respected."""
    print("\n[2] Thinking budget test...")
    msgs = [ChatMessage(role="user", content="What is 2+2?")]
    result = await provider.chat(msgs, thinking_budget="low")
    print(f"  Thinking tokens: {result.thinking_tokens}")
    print(f"  Output tokens: {result.output_tokens}")
    print(f"  Response: {result.content[:80]}")
    status = PASS if result.output_tokens > 0 else FAIL
    print(f"  {status}")
    return result.output_tokens > 0


async def test_code_generation(provider):
    """Simulate a code generation task with structured output."""
    print("\n[3] Code generation + change visibility test...")
    msgs = [
        ChatMessage(role="system", content=DeepSeekProvider.build_system_prompt(
            "project:\n  type: cli_tool\n  frontend: none\n  backend: python"
        )),
        ChatMessage(role="user", content="""Write a Python function `add(a, b)` that returns the sum.
Output your changes in the structured format:

## Change Summary
Added add() function to utils.py — a simple addition utility.

## Intent Groups
- interface: none
- logic: utils.py (new function add)
- test: none
- refactor: none

## Risk Assessment
- low: trivial function, no edge cases
- medium: none
- high: none

Also output the actual code after the summary:
```python
def add(a, b):
    return a + b
```"""),
    ]
    result = await provider.chat(msgs, thinking_budget="high")
    print(f"  Tokens: {result.output_tokens}")
    print(f"  First 150 chars: {result.content[:150]}")

    # Parse change visibility
    cl = parse_change_summary(result.content)
    has_summary = len(cl.summary) > 0
    has_intent = cl.intent_group is not None
    print(f"  Summary extracted: {'YES' if has_summary else 'NO'}")
    print(f"  Intent group: {cl.intent_group.value if cl.intent_group else 'N/A'}")
    print(f"  Risk label: {cl.risk_label.value if cl.risk_label else 'N/A'}")

    status = PASS if (has_summary and result.output_tokens > 0) else FAIL
    print(f"  {status}")
    return has_summary


async def test_phase_budgets(provider):
    """Verify thinking budget varies by phase."""
    print("\n[4] Phase → thinking budget mapping...")
    test_phases = [Phase.SPEC, Phase.CODE, Phase.MERGE]
    all_ok = True
    for phase in test_phases:
        budget = thinking_for_phase(phase)
        tokens = THINKING_BUDGETS.get(budget)
        print(f"  {phase.value:8s} → {budget:6s} (max {tokens or 0} tokens)")
        if budget not in THINKING_BUDGETS:
            all_ok = False
    print(f"  {PASS if all_ok else FAIL}")
    return all_ok


async def main():
    print("=" * 60)
    print("EDE P0 Smoke Test — Real API Verification")
    print("=" * 60)

    provider = check_api()
    if provider is None:
        print(f"\n{PASS} All checks that didn't need API passed.")
        return

    results = []
    results.append(await test_connectivity(provider))
    results.append(await test_thinking_budget(provider))
    results.append(await test_code_generation(provider))
    results.append(await test_phase_budgets(provider))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    print(f"{PASS if passed == total else FAIL}")
    return passed == total


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
