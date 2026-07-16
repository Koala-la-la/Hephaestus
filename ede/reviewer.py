"""Reviewer Orchestrator — parallel multi-reviewer code review.

Spec FR-006:
  After code generation completes, spawn multiple reviewer agents in parallel
  (spec compliance, robustness, standards). Aggregate results into a structured
  review report for the engineer.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from ede.llm_adapter import DeepSeekProvider, ChatMessage
from ede.models import Phase


@dataclass
class Reviewer:
    """A single reviewer agent definition."""
    name: str
    dimension: str  # e.g. "spec_compliance", "robustness", "standards"
    system_prompt: str
    review_prompt_template: str  # {spec} and {diff} as placeholders


@dataclass
class ReviewFinding:
    reviewer: str
    dimension: str
    severity: str  # "error" | "warning" | "info"
    file: str = ""
    line: str = ""
    message: str = ""


@dataclass
class ReviewReport:
    task_id: str
    findings: list[ReviewFinding] = field(default_factory=list)
    summary: str = ""
    total_errors: int = 0
    total_warnings: int = 0

    def to_markdown(self) -> str:
        lines = ["## Review Report", f"", f"**Task**: {self.task_id}"]
        lines.append(f"**Errors**: {self.total_errors} | **Warnings**: {self.total_warnings}")
        lines.append("")
        if self.summary:
            lines.append(f"**Summary**: {self.summary}")
            lines.append("")

        by_dim = {}
        for f in self.findings:
            by_dim.setdefault(f.dimension, []).append(f)

        for dim, findings in by_dim.items():
            lines.append(f"### {dim}")
            for f in findings:
                icon = {"error": "X", "warning": "!!", "info": "i"}.get(f.severity, "?")
                loc = f" ({f.file}:{f.line})" if f.file else ""
                lines.append(f"- [{icon}] {f.message}{loc}")
            lines.append("")
        return "\n".join(lines)


class ReviewerOrchestrator:
    """Spawns multiple reviewers in parallel and aggregates findings."""

    def __init__(self, provider: DeepSeekProvider):
        self.provider = provider
        self._reviewers: list[Reviewer] = []
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in reviewers (spec §FR-006)."""

        self._reviewers.append(Reviewer(
            name="spec-compliance",
            dimension="Spec Compliance",
            system_prompt="""You are a spec-compliance reviewer. Your job is to verify that
the code changes match the specification exactly. Check:
1. All acceptance criteria from the spec are addressed
2. No functionality beyond the spec was added (scope creep)
3. Edge cases mentioned in the spec are handled

Report findings as:
- [error] spec violation (must fix)
- [warning] potential gap
- [info] observation""",
            review_prompt_template="""Review these code changes against the specification:

Spec: {spec}

Changes: {diff}

Output findings one per line:
severity|file|message""",
        ))

        self._reviewers.append(Reviewer(
            name="robustness",
            dimension="Robustness",
            system_prompt="""You are a robustness reviewer. Check code for:
1. Error handling — are exceptions caught appropriately?
2. Input validation — are inputs sanitized and validated?
3. Edge cases — null/empty inputs, boundary values
4. Resource management — are files, connections, locks properly released?

Report findings one per line:
severity|file|message""",
            review_prompt_template="""Review these code changes for robustness issues:

Changes: {diff}

Output findings one per line:
severity|file|message""",
        ))

        self._reviewers.append(Reviewer(
            name="standards",
            dimension="Code Standards",
            system_prompt="""You are a code standards reviewer. Check:
1. Naming conventions are consistent
2. Functions are single-responsibility
3. No dead code or commented-out code
4. Comments explain WHY not WHAT
5. No hardcoded secrets or magic numbers

Report findings one per line:
severity|file|message""",
            review_prompt_template="""Review these code changes for standards issues:

Changes: {diff}

Output findings one per line:
severity|file|message""",
        ))

    def add_reviewer(self, reviewer: Reviewer):
        self._reviewers.append(reviewer)

    async def review(self, task_id: str, spec_text: str, diff_text: str) -> ReviewReport:
        """Run all reviewers in parallel and aggregate results."""
        report = ReviewReport(task_id=task_id)

        async def run_one(reviewer: Reviewer) -> list[ReviewFinding]:
            prompt = reviewer.review_prompt_template.format(
                spec=spec_text[:4000], diff=diff_text[:4000]
            )
            msgs = [
                ChatMessage(role="system", content=reviewer.system_prompt),
                ChatMessage(role="user", content=prompt),
            ]
            result = await self.provider.chat(msgs, thinking_budget="medium")
            return self._parse_findings(reviewer, result.content)

        # Parallel execution
        all_findings = await asyncio.gather(*[run_one(r) for r in self._reviewers])

        for findings in all_findings:
            report.findings.extend(findings)

        report.total_warnings = sum(
            1 for f in report.findings if f.severity == "warning"
        )
        report.total_errors = sum(
            1 for f in report.findings if f.severity == "error"
        )

        if not report.findings:
            report.summary = "No issues found by automated review."
        elif report.total_errors == 0:
            report.summary = f"{report.total_warnings} warning(s) found, no errors."
        else:
            report.summary = (
                f"{report.total_errors} error(s), {report.total_warnings} warning(s) "
                f"found across {len(set(f.dimension for f in report.findings))} dimensions."
            )

        return report

    def _parse_findings(self, reviewer: Reviewer, content: str) -> list[ReviewFinding]:
        findings = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("```"):
                continue
            parts = line.split("|", 2)
            if len(parts) >= 3:
                severity = parts[0].strip().lower()
                file = parts[1].strip()
                message = parts[2].strip()
                if severity in ("error", "warning", "info"):
                    findings.append(ReviewFinding(
                        reviewer=reviewer.name,
                        dimension=reviewer.dimension,
                        severity=severity,
                        file=file,
                        message=message,
                    ))
            elif len(parts) == 1 and any(
                kw in line.lower() for kw in ("error", "warning", "info", "issue", "missing")
            ):
                findings.append(ReviewFinding(
                    reviewer=reviewer.name,
                    dimension=reviewer.dimension,
                    severity="warning",
                    message=line,
                ))
        return findings
