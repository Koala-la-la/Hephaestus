"""Self-Refinement Engine — error-driven context evolution.

Spec FR-007:
  Detects error patterns from audit logs, recommends context.yaml updates,
  and applies them with user confirmation. Ensures "be corrected errors don't repeat".
"""

import pathlib
import yaml
from typing import Optional


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

            if "l3_blocked" in action:
                key = f"history:{detail}"
                if key not in seen:
                    seen.add(key)
                    suggestions.append({
                        "type": "history",
                        "content": f"L3 gate blocked: {detail}",
                        "source": f"audit_log:{action}",
                    })
            elif "gates_failed" in action or "blocked" in action:
                key = f"constraint:{detail}"
                if key not in seen:
                    seen.add(key)
                    suggestions.append({
                        "type": "constraint",
                        "content": f"Gate failure: {detail}",
                        "source": f"audit_log:{action}",
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
            if s["type"] == "constraint":
                constraints = ctx.setdefault("constraints", [])
                if content not in constraints:
                    constraints.append(content)
                    updated += 1
                else:
                    skipped += 1
            elif s["type"] == "history":
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
        lines = ["Self-Refinement suggestions:"]
        for i, s in enumerate(suggestions, 1):
            lines.append(f"  {i}. [{s['type']}] {s['content'][:80]}")
        return "\n".join(lines)
