"""Data classes and SQLite schema for the EDE pipeline.

Schema mirrors spec §5.2:
  Project 1──N Task 1──N ChangeLog
  Task 1──N Checkpoint / GateResult / AuditLog
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json


# ── Enums ──────────────────────────────────────────────

class Phase(str, Enum):
    SPEC = "spec"
    DESIGN = "design"
    PLAN = "plan"
    CODE = "code"
    TEST = "test"
    REVIEW = "review"
    MERGE = "merge"

    @classmethod
    def next_phase(cls, current: "Phase") -> Optional["Phase"]:
        order = list(cls)
        idx = order.index(current)
        return order[idx + 1] if idx + 1 < len(order) else None


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAIT_USER = "wait_user"
    DONE = "done"
    BLOCKED = "blocked"


class CheckpointStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    TIMEOUT = "timeout"


class IntentGroup(str, Enum):
    INTERFACE = "interface"
    LOGIC = "logic"
    TEST = "test"
    REFACTOR = "refactor"


class RiskLabel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Data Classes ───────────────────────────────────────

@dataclass
class Project:
    project_id: str
    name: str
    config_path: str = ""
    context_md5: str = ""

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "config_path": self.config_path,
            "context_md5": self.context_md5,
        }


@dataclass
class Task:
    task_id: str
    project_id: str
    phase: Phase = Phase.SPEC
    status: TaskStatus = TaskStatus.PENDING
    stage_data: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "phase": self.phase.value,
            "status": self.status.value,
            "stage_data": json.dumps(self.stage_data, ensure_ascii=False),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Checkpoint:
    task_id: str
    stage: str
    status: CheckpointStatus = CheckpointStatus.PENDING
    confirmed_at: str = ""
    confirmed_by: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "stage": self.stage,
            "status": self.status.value,
            "confirmed_at": self.confirmed_at,
            "confirmed_by": self.confirmed_by,
        }


@dataclass
class GateResult:
    task_id: str
    gate_name: str
    passed: bool = False
    detail: str = ""
    checked_at: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "gate_name": self.gate_name,
            "passed": self.passed,
            "detail": self.detail,
            "checked_at": self.checked_at,
        }


@dataclass
class AuditLog:
    task_id: str
    action: str
    detail: str
    operator: str = "system"
    irreversible: bool = True

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "action": self.action,
            "detail": self.detail,
            "operator": self.operator,
            "irreversible": self.irreversible,
        }


@dataclass
class ChangeLog:
    change_id: str
    task_id: str
    spec_ref: str = ""
    intent_group: IntentGroup = IntentGroup.LOGIC
    summary: str = ""
    risk_label: RiskLabel = RiskLabel.LOW
    diff_hash: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "change_id": self.change_id,
            "task_id": self.task_id,
            "spec_ref": self.spec_ref,
            "intent_group": self.intent_group.value,
            "summary": self.summary,
            "risk_label": self.risk_label.value,
            "diff_hash": self.diff_hash,
            "created_at": self.created_at,
        }


# ── SQL DDL ────────────────────────────────────────────

DDL_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS project (
    project_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    config_path TEXT DEFAULT '',
    context_md5 TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS task (
    task_id     TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    phase       TEXT NOT NULL DEFAULT 'spec',
    status      TEXT NOT NULL DEFAULT 'pending',
    stage_data  TEXT DEFAULT '{}',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES project(project_id)
);

CREATE TABLE IF NOT EXISTS checkpoint (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT NOT NULL,
    stage        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    confirmed_at TEXT DEFAULT '',
    confirmed_by TEXT DEFAULT '',
    FOREIGN KEY (task_id) REFERENCES task(task_id)
);

CREATE TABLE IF NOT EXISTS gate_result (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL,
    gate_name  TEXT NOT NULL,
    passed     INTEGER NOT NULL DEFAULT 0,
    detail     TEXT DEFAULT '',
    checked_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES task(task_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT NOT NULL,
    action       TEXT NOT NULL,
    detail       TEXT DEFAULT '',
    operator     TEXT DEFAULT 'system',
    irreversible INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES task(task_id)
);

CREATE TABLE IF NOT EXISTS change_log (
    change_id    TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL,
    spec_ref     TEXT DEFAULT '',
    intent_group TEXT NOT NULL DEFAULT 'logic',
    summary      TEXT DEFAULT '',
    risk_label   TEXT NOT NULL DEFAULT 'low',
    diff_hash    TEXT DEFAULT '',
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES task(task_id)
);
"""
