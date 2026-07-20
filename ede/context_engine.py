"""Context Engine — project context management and prompt injection.

Spec §5.3:
  Reads .ede/context.yaml, resolves project-specific conventions and constraints,
  injects them into LLM system prompts.
"""

import pathlib
import hashlib
from typing import Optional
from dataclasses import dataclass, field

import yaml


DEFAULT_CONTEXT = {
    "project": {"type": "", "frontend": "", "backend": "", "database": ""},
    "conventions": {"naming": "snake_case", "api_style": "rest"},
    "constraints": [],
    "history": [],
}


@dataclass
class ProjectContext:
    """Parsed project context from .ede/context.yaml."""
    project_type: str = ""
    frontend: str = ""
    backend: str = ""
    database: str = ""
    naming: str = "snake_case"
    api_style: str = "rest"
    auth: str = ""
    constraints: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)

    def to_yaml_text(self) -> str:
        """Serialize back to YAML text for prompt injection."""
        data = {
            "project": {
                "type": self.project_type,
                "frontend": self.frontend,
                "backend": self.backend,
                "database": self.database,
            },
            "conventions": {
                "naming": self.naming,
                "api_style": self.api_style,
            },
        }
        if self.auth:
            data["conventions"]["auth"] = self.auth
        if self.constraints:
            data["constraints"] = self.constraints
        if self.history:
            data["history"] = self.history

        return yaml.dump(data, allow_unicode=True, default_flow_style=False)

    def to_prompt_prefix(self) -> str:
        """Generate a prompt prefix summarising the project context."""
        lines = ["Project context:"]
        if self.project_type:
            lines.append(f"  Type: {self.project_type}")
        if self.frontend:
            lines.append(f"  Frontend: {self.frontend}")
        if self.backend:
            lines.append(f"  Backend: {self.backend}")
        if self.database:
            lines.append(f"  Database: {self.database}")
        lines.append(f"  Naming: {self.naming}")
        lines.append(f"  API: {self.api_style}")
        if self.constraints:
            lines.append("  Constraints:")
            for c in self.constraints:
                lines.append(f"    - {c}")
        if self.history:
            lines.append("  History (past mistakes to avoid):")
            for h in self.history[-3:]:  # most recent 3
                lines.append(f"    - {h}")
        return "\n".join(lines)




# ── Trust Tier ─────────────────────────────────────────

class TrustConfig:
    """Trust tier configuration for adaptive constraint enforcement."""

    VALID_TIERS = ("T0", "T1", "T2", "T3")

    def __init__(self, tier: str = "T1", overrides: dict[str, str] = None):
        self.tier = tier if tier in self.VALID_TIERS else "T1"
        self.overrides = overrides or {}

    @classmethod
    def from_yaml(cls, path: pathlib.Path = None) -> "TrustConfig":
        """Load trust config from .ede/config.yaml. Returns defaults if missing."""
        if path is None:
            path = pathlib.Path(".ede/config.yaml")
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        trust = raw.get("trust", {})
        return cls(
            tier=trust.get("tier", "T1"),
            overrides=trust.get("overrides", {}),
        )

    def effective_tier(self, phase: str) -> str:
        """Return the trust tier for a given phase, respecting overrides."""
        return self.overrides.get(phase, self.tier)

    def should_block_human_checkpoint(self, phase: str) -> bool:
        """T0 blocks human checkpoints. T1+ passes automatically."""
        return self.effective_tier(phase) == "T0"

    def should_block_on_l3_failure(self, phase: str) -> bool:
        """T0-T1 block on L3 failure. T2-T3 notify only."""
        return self.effective_tier(phase) in ("T0", "T1")

    def max_auto_retries(self, phase: str, gate_level: int) -> int:
        """Return max retries for a gate at a given trust tier.
        T0: L1=2, L2=1, L3=0
        T1: L1=2, L2=1, L3=0
        T2: L1=3, L2=2, L3=1
        T3: L1=3, L2=3, L3=1 (notify only)
        """
        tier = self.effective_tier(phase)
        tiers = {
            "T0": {1: 2, 2: 1, 3: 0},
            "T1": {1: 2, 2: 1, 3: 0},
            "T2": {1: 3, 2: 2, 3: 1},
            "T3": {1: 3, 2: 3, 3: 1},
        }
        return tiers.get(tier, {}).get(gate_level, 0)


class ContextEngine:
    """Loads, parses, and injects project context into LLM prompts."""

    def __init__(self, project_root: str = "."):
        self.root = pathlib.Path(project_root)
        self.config_path = self.root / ".ede" / "context.yaml"
        self._cache: Optional[ProjectContext] = None
        self._cache_md5: str = ""

    def load(self) -> ProjectContext:
        """Load and parse context.yaml. Returns defaults if file missing."""
        if not self.config_path.exists():
            return ProjectContext()

        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        project = raw.get("project", {})
        conventions = raw.get("conventions", {})

        ctx = ProjectContext(
            project_type=project.get("type", ""),
            frontend=project.get("frontend", ""),
            backend=project.get("backend", ""),
            database=project.get("database", ""),
            naming=conventions.get("naming", "snake_case"),
            api_style=conventions.get("api_style", "rest"),
            auth=conventions.get("auth", ""),
            constraints=raw.get("constraints", []),
            history=raw.get("history", []),
        )
        self._cache = ctx
        return ctx

    def get_context_md5(self) -> str:
        """Return MD5 hash of the context.yaml contents for change detection."""
        if self.config_path.exists():
            return hashlib.md5(
                self.config_path.read_bytes()
            ).hexdigest()
        return ""

    def resolve(self, task: Optional[dict] = None) -> str:
        """Resolve full project context as a prompt prefix string.

        Args:
            task: optional task dict with phase info

        Returns:
            Natural-language context string for LLM system prompt.
        """
        ctx = self.load()
        return ctx.to_prompt_prefix()
