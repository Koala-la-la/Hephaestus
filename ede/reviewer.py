"""Reviewer Orchestrator — parallel multi-reviewer code review.

Spec FR-006:
  After code generation completes, spawn multiple reviewer agents in parallel
  (spec compliance, robustness, standards). Aggregate results into a structured
  review report for the engineer.
"""

import asyncio
import re
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

    def _register_accuracy_reviewer(self):
        """Register the accuracy reviewer that cross-validates Agent self-assessment."""
        self._reviewers.append(Reviewer(
            name="accuracy",
            dimension="Accuracy",
            system_prompt="""You are an accuracy reviewer. Your sole job is to compare the
Agent's self-assessment (change summary, intent groups, risk labels)
against the actual diff, and flag every disagreement.

Core rule — **Mandatory Citation**:
For EVERY disagreement you report, you MUST:
  1. Quote the Agent's claim verbatim
  2. Point to at least one specific diff line (with line number) that contradicts it
  3. Copy-paste the exact diff line as evidence

Output format (one finding per line, pipe-separated):
  severity|file|line_number|agent_claim|reviewer_reason|diff_quote

Rules:
- severity: "error" if the Agent clearly mislabeled a high-risk change as low-risk.
            "warning" if the Agent omitted or understated a meaningful change.
- line_number: the exact line from the diff that proves the disagreement.
- diff_quote: copy-paste the **verbatim** diff line. Leave empty ONLY if you have
  no disagreement.

WARNING: Findings without a valid line_number AND a non-empty diff_quote
will be **silently discarded**. You must provide both.""" ,
            review_prompt_template="""Compare the Agent's self-assessment against the actual diff.

=== AGENT SELF-ASSESSMENT ===
{spec}

=== ACTUAL DIFF ===
{diff}

Output findings (one per line):
  severity|file|line_number|agent_claim|reviewer_reason|diff_quote

If the Agent's assessment is fully accurate, output a single line:
  info||-|Accurate self-assessment||""",
        ))

    async def review_accuracy(
        self, task_id: str, agent_self_assessment: str, diff_text: str
    ) -> ReviewReport:
        """Run accuracy reviewer against Agent's self-assessment.

        Returns a ReviewReport where total_errors > 0 means the Agent's
        assessment is inaccurate and human review is mandatory.
        """
        accuracy_reviewer = None
        for r in self._reviewers:
            if r.name == "accuracy":
                accuracy_reviewer = r
                break

        if accuracy_reviewer is None:
            self._register_accuracy_reviewer()
            accuracy_reviewer = self._reviewers[-1]

        report = ReviewReport(task_id=task_id)

        prompt = accuracy_reviewer.review_prompt_template.format(
            spec=agent_self_assessment[:4000],
            diff=diff_text[:4000],
        )
        msgs = [
            ChatMessage(role="system", content=accuracy_reviewer.system_prompt),
            ChatMessage(role="user", content=prompt),
        ]
        result = await self.provider.chat(msgs, thinking_budget="medium")

        # Use citation-aware parser for accuracy findings
        findings = self._parse_findings_with_citations(accuracy_reviewer, result.content)
        report.findings = findings
        report.total_errors = sum(1 for f in findings if f.severity == "error")
        report.total_warnings = sum(1 for f in findings if f.severity == "warning")

        if not findings:
            report.summary = "Agent self-assessment is accurate."
        elif report.total_errors == 0:
            report.summary = (
                f"{report.total_warnings} disagreement(s) found — "
                "Agent assessment mostly accurate, minor discrepancies."
            )
        else:
            report.summary = (
                f"{report.total_errors} error(s), {report.total_warnings} warning(s) — "
                "Agent self-assessment is INACCURATE. Human review MANDATORY."
            )

        return report

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

    # ── Finding parsers ──────────────────────────────

    _SEVERITY_TAG_RE = re.compile(
        r"\[(error|warning|info)\]",
        re.IGNORECASE,
    )
    _ACCURACY_SEVERITY_RE = re.compile(r"^(error|warning|info)\|", re.IGNORECASE)

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
                continue

            # Fallback 1: severity tag [error] / [warning] / [info]
            tag_m = self._SEVERITY_TAG_RE.search(line)
            if tag_m:
                findings.append(ReviewFinding(
                    reviewer=reviewer.name,
                    dimension=reviewer.dimension,
                    severity=tag_m.group(1).lower(),
                    message=line,
                ))
                continue

            # Fallback 2: unstructured line → warning
            if len(line) > 5 and not line.startswith("#") and not line.startswith("!"):
                findings.append(ReviewFinding(
                    reviewer=reviewer.name,
                    dimension=reviewer.dimension,
                    severity="warning",
                    message=line,
                ))

        return findings

    def _parse_findings_with_citations(
        self, reviewer: Reviewer, content: str
    ) -> list[ReviewFinding]:
        """Parse accuracy-review output with mandatory citation format.

        Expected format:
          severity|file|line_number|agent_claim|reviewer_reason|diff_quote

        Findings missing line_number or diff_quote are silently dropped.
        """
        findings = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("```"):
                continue
            if not self._ACCURACY_SEVERITY_RE.match(line):
                continue
            parts = line.split("|", 5)
            if len(parts) < 6:
                continue
            severity = parts[0].strip().lower()
            if severity not in ("error", "warning", "info"):
                continue
            file = parts[1].strip()
            line_number_raw = parts[2].strip()
            agent_claim = parts[3].strip()
            reviewer_reason = parts[4].strip()
            diff_quote = parts[5].strip()
            # Mandatory citation guards
            if not line_number_raw.isdigit():
                continue
            if not diff_quote:
                continue
            message = (
                f"Agent claimed: <{agent_claim}> — "
                f"Reviewer: {reviewer_reason} "
                f"(L{line_number_raw}: ...{diff_quote[:80]}...)"
            )
            findings.append(ReviewFinding(
                reviewer=reviewer.name,
                dimension=reviewer.dimension,
                severity=severity,
                file=file,
                line=line_number_raw,
                message=message,
            ))
        return findings