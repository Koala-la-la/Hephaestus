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
