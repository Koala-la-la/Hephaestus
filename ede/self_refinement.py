"""Self-Refinement Engine — error-driven context evolution.

Spec FR-007:
  Detects error patterns from audit logs, categorizes by type,
  recommends context.yaml updates, and applies them.
"""

import pathlib
import yaml
from typing import Optional


# ── Pattern categories ───────────────────────────────

PATTERN_RULES = [
    # (action_keyword, category, suggestion_prefix)
    ("l3_blocked", "history", "L3 gate blocked — needs human decision"),
    ("gates_failed", "constraint", "Gate failure pattern"),
    ("blocked_prereqs", "constraint", "Prerequisite not met"),
    ("review_complete", "review", "Review findings"),
    ("accuracy_blocked", "review", "Agent self-assessment inaccurate"),
    ("gates_auto_retry_exhausted", "workflow", "Auto-retry limit reached"),
    ("phase_skipped", "workflow", "Phase was skipped"),
    ("checkpoint_confirmed", "workflow", "Checkpoint confirmed"),
]


class SelfRefinement:
    """Analyzes audit logs to detect error patterns and suggest improvements."""

    def __init__(self, project_root: str = "."):
        self.root = pathlib.Path(project_root)
        self.context_path = self.root / ".ede" / "context.yaml"

    def analyze(self, audit_logs: list[dict]) -> list[dict]:
        suggestions = []
        seen = set()

        for entry in audit_logs:
            action = entry.get("action", "")
            detail = entry.get("detail", "")

            matched = False
            for keyword, category, prefix in PATTERN_RULES:
                if keyword in action:
                    key = f"{category}:{detail[:80]}"
                    if key not in seen:
                        seen.add(key)
                        suggestions.append({
                            "type": category,
                            "content": f"{prefix}: {detail[:120]}",
                            "source": f"audit_log:{action}",
                            "severity": self._severity(category),
                        })
                    matched = True
                    break

            # Catch unclassified blocked actions
            if not matched and ("blocked" in action or "failed" in action):
                key = f"constraint:{detail[:80]}"
                if key not in seen:
                    seen.add(key)
                    suggestions.append({
                        "type": "constraint",
                        "content": f"Unclassified failure: {detail[:120]}",
                        "source": f"audit_log:{action}",
                        "severity": "medium",
                    })

        return suggestions

    def apply(self, suggestions: list[dict]) -> dict:
        if not self.context_path.exists():
            return {"updated": 0, "skipped": len(suggestions), "errors": ["context.yaml not found"]}

        ctx = yaml.safe_load(self.context_path.read_text(encoding="utf-8")) or {}
        updated = 0
        skipped = 0

        for s in suggestions:
            content = s["content"]
            category = s["type"]

            if category == "constraint":
                constraints = ctx.setdefault("constraints", [])
                if content not in constraints:
                    constraints.append(content)
                    updated += 1
                else:
                    skipped += 1
            elif category in ("history", "workflow", "review"):
                history = ctx.setdefault("history", [])
                if content not in history:
                    history.append(content)
                    updated += 1
                else:
                    skipped += 1

        if updated > 0:
            self.context_path.write_text(
                yaml.dump(ctx, allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )

        return {"updated": updated, "skipped": skipped, "errors": []}

    def get_suggestions_summary(self, suggestions: list[dict]) -> str:
        if not suggestions:
            return "No new suggestions."

        by_category = {}
        for s in suggestions:
            by_category.setdefault(s.get("type", "unknown"), []).append(s)

        lines = [f"Self-Refinement: {len(suggestions)} suggestion(s)"]
        for cat, items in by_category.items():
            lines.append(f"  [{cat}] {len(items)}:")
            for item in items[:3]:
                sev = item.get("severity", "")
                marker = {"high": "[‼]", "medium": "[!!]", "low": "[i]"}.get(sev, "")
                lines.append(f"    {marker} {item['content'][:80]}")
            if len(items) > 3:
                lines.append(f"    ... and {len(items)-3} more")
        return "\n".join(lines)

    @staticmethod
    def _severity(category: str) -> str:
        return {
            "history": "high",
            "constraint": "medium",
            "review": "high",
            "workflow": "low",
        }.get(category, "low")
