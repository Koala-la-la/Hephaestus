"""Change Visibility Engine — parses LLM output into structured ChangeLog entries.

Spec §3.2 FR-003:
  (1) Change summary — what, why, how
  (2) Diff grouped by intent — interface / logic / test / refactor
  (3) Risk label — low / medium / high
  (4) Change history timeline linked to spec refs
"""

import re
import uuid
import hashlib

from ede.models import ChangeLog, IntentGroup, RiskLabel


def parse_change_summary(llm_output: str) -> ChangeLog:
    """Parse LLM output into a structured ChangeLog."""
    change_id = str(uuid.uuid4())[:8]
    summary = _extract_section(llm_output, "Change Summary")
    intent = _extract_intent_groups(llm_output)
    risk = _extract_risk_label(llm_output)
    return ChangeLog(
        change_id=change_id,
        task_id="",
        summary=summary,
        intent_group=intent,
        risk_label=risk,
        diff_hash=hashlib.md5(llm_output.encode()).hexdigest()[:12],
    )


def _extract_section(text: str, heading: str) -> str:
    """Extract content under a markdown heading."""
    hdr = "## " + heading
    idx = text.find(hdr)
    if idx == -1:
        return ""
    start = idx + len(hdr)
    rest = text[start:]
    # Find next ## heading or end
    m = re.search(r"\n## ", rest)
    end = start + m.start() if m else len(text)
    return text[start:end].strip()


def _extract_intent_groups(text: str) -> IntentGroup:
    """Determine primary intent group from the LLM output."""
    content = _extract_section(text, "Intent Groups")
    if not content:
        return IntentGroup.LOGIC
    groups = {}
    for line in content.split("\n"):
        ls = line.strip()
        for label in ("logic", "interface", "test", "refactor"):
            if ls.lower().startswith("- " + label):
                rest = ls[len("- " + label):].strip(": ").strip()
                groups[label] = rest
    for key in ("logic", "interface", "test", "refactor"):
        if groups.get(key):
            return IntentGroup(key)
    return IntentGroup.LOGIC


def _extract_risk_label(text: str) -> RiskLabel:
    """Extract highest risk level."""
    content = _extract_section(text, "Risk Assessment")
    if not content:
        return RiskLabel.LOW
    high_items = _items_under(content, "high")
    medium_items = _items_under(content, "medium")
    # Filter out "none" placeholders
    high_real = [i for i in high_items if i.lower().strip("-: ").strip() not in ("", "none")]
    medium_real = [i for i in medium_items if i.lower().strip("-: ").strip() not in ("", "none")]
    if high_real:
        return RiskLabel.HIGH
    if medium_real:
        return RiskLabel.MEDIUM
    return RiskLabel.LOW


def _items_under(text: str, label: str) -> list[str]:
    """Extract bullet items under a label within Risk Assessment."""
    tag = "- " + label + ":"
    idx = text.find(tag)
    if idx == -1:
        return []
    start = idx + len(tag)
    rest = text[start:]
    m = re.search(r"\n- \w+:", rest)
    end = start + m.start() if m else len(text)
    return [l.strip() for l in text[start:end].strip().split("\n") if l.strip()]


def parse_change_entries(llm_output: str, change_id: str) -> list:
    """Parse LLM output into multiple ChangeEntry objects (one per intent group).

    Each intent group with files becomes a separate ChangeEntry.
    """
    from ede.models import ChangeEntry, IntentGroup, RiskLabel, AccuracyScore
    import uuid

    entries = []
    content = _extract_section(llm_output, "Intent Groups")
    if not content:
        # Fallback: create a single entry from the full summary
        summary = _extract_section(llm_output, "Change Summary")
        risk = _extract_risk_label(llm_output)
        return [ChangeEntry(
            entry_id=str(uuid.uuid4())[:8],
            change_id=change_id,
            intent_group=IntentGroup.LOGIC,
            agent_risk_label=risk,
            effective_risk_label=risk,
            summary=summary,
        )]

    # Extract per-group items
    group_files = {}
    for line in content.split("\n"):
        ls = line.strip()
        for label in ("interface", "logic", "test", "refactor"):
            if ls.lower().startswith("- " + label):
                rest = ls[len("- " + label):].strip(": ").strip()
                if rest and rest.lower() != "none":
                    group_files.setdefault(label, []).append(rest)

    # Determine risk per file group from Risk Assessment
    risk_section = _extract_section(llm_output, "Risk Assessment")
    risks = _extract_risk_by_group(risk_section)

    for group, files in group_files.items():
        for file_ref in files:
            entry = ChangeEntry(
                entry_id=str(uuid.uuid4())[:8],
                change_id=change_id,
                intent_group=IntentGroup(group),
                agent_risk_label=RiskLabel(risks.get(group, "low")),
                effective_risk_label=RiskLabel(risks.get(group, "low")),
                file_path=file_ref,
                summary=_extract_section(llm_output, "Change Summary"),
            )
            entries.append(entry)

    if not entries:
        # Fallback single entry
        summary = _extract_section(llm_output, "Change Summary")
        risk = _extract_risk_label(llm_output)
        entries.append(ChangeEntry(
            entry_id=str(uuid.uuid4())[:8],
            change_id=change_id,
            intent_group=IntentGroup.LOGIC,
            agent_risk_label=risk,
            effective_risk_label=risk,
            summary=summary,
        ))

    return entries


def _extract_risk_by_group(risk_text: str) -> dict[str, str]:
    """Map intent groups to risk levels from Risk Assessment section."""
    result = {}
    current_group = ""
    for line in risk_text.split("\n"):
        ls = line.strip()
        for label in ("high", "medium", "low"):
            if ls.lower().startswith("- " + label + ":"):
                current_label = label
                rest = ls[len("- " + label + ":"):].strip()
                if rest and rest.lower() not in ("none", ""):
                    for group in ("interface", "logic", "test", "refactor"):
                        if group in rest.lower():
                            result[group] = label
                break
    return result


def build_change_summary_prompt(task_description: str) -> str:
    """Build a prompt that asks the LLM to self-summarize its code changes."""
    return f"""After making code changes for the task below, output a structured change summary:

Task: {task_description}

Output format:
```
## Change Summary
[2-3 sentences describing what was changed, why, and how]

## Intent Groups
- interface: [list files with API/signature changes, or "none"]
- logic: [list files with business logic changes, or "none"]
- test: [list test files added/modified, or "none"]
- refactor: [list files restructured without behavior change, or "none"]

## Risk Assessment
- low: [changes that are straightforward, well-tested, or cosmetic]
- medium: [changes that affect multiple modules or have edge cases]
- high: [changes that affect core logic, data integrity, or concurrency]
```
"""
