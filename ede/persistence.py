"""SQLite persistence layer.

Manages DB initialization, migrations, and CRUD for all entities.
All mutations write to disk immediately. Uses WAL mode for concurrency.
"""

import hashlib
import sqlite3
import pathlib
from typing import Optional

from ede.models import (
    DDL_CREATE_TABLES,
    ChangeLog, ChangeEntry, DisagreementEvidence,
    IntentGroup, RiskLabel,
)


# ── Schema version (simple migration support) ───────

SCHEMA_VERSION = 2
MIGRATIONS = {
    2: """
        CREATE TABLE IF NOT EXISTS change_entry (
            entry_id             TEXT PRIMARY KEY,
            change_id            TEXT NOT NULL,
            intent_group         TEXT NOT NULL DEFAULT 'logic',
            agent_risk_label     TEXT NOT NULL DEFAULT 'low',
            effective_risk_label TEXT NOT NULL DEFAULT 'low',
            accuracy_score       TEXT DEFAULT '',
            file_path            TEXT DEFAULT '',
            summary              TEXT DEFAULT '',
            created_at           TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (change_id) REFERENCES change_log(change_id)
        );

        CREATE TABLE IF NOT EXISTS disagreement_evidence (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id        TEXT NOT NULL,
            reviewer        TEXT NOT NULL,
            severity        TEXT NOT NULL,
            file_path       TEXT DEFAULT '',
            line_number     INTEGER NOT NULL DEFAULT 0,
            agent_claim     TEXT DEFAULT '',
            reviewer_reason TEXT DEFAULT '',
            diff_quote      TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entry_id) REFERENCES change_entry(entry_id)
        );
    """,
}


class Persistence:
    """SQLite-backed persistence for EDE state."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def init_db(self) -> None:
        """Create database file, run schema DDL, apply migrations."""
        pathlib.Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript(DDL_CREATE_TABLES)
            conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Apply pending schema migrations."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("PRAGMA user_version;")
            current = cur.fetchone()[0]
        for version in sorted(MIGRATIONS):
            if version > current:
                with sqlite3.connect(self.db_path) as conn:
                    conn.executescript(MIGRATIONS[version])
                    conn.execute(f"PRAGMA user_version = {version};")
                    conn.commit()

    def schema_version(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("PRAGMA user_version;")
            return cur.fetchone()[0]

    # ── Schema inspection ─────────────────────────────

    def has_table(self, table_name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return cursor.fetchone() is not None

    def table_count(self, table_name: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]

    def get_tables(self) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            return [r[0] for r in rows]

    # ── Project ───────────────────────────────────────

    def insert_project(self, project_id: str, name: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO project (project_id, name) VALUES (?, ?)",
                (project_id, name),
            )
            conn.commit()

    def get_project(self, project_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM project WHERE project_id=?", (project_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── Task ──────────────────────────────────────────

    def create_task(self, task_id: str, project_id: str, description: str = "",
                    start_phase: str = "spec", **kwargs) -> None:
        """Create a new task, optionally at a later phase."""
        import json
        valid = {"spec", "design", "plan", "code", "test", "review", "merge"}
        if start_phase not in valid:
            start_phase = "spec"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO task (task_id, project_id, phase, status, stage_data, depends_on)
                   VALUES (?, ?, ?, 'pending', ?, ?)""",
                (task_id, project_id, start_phase,
                 json.dumps({"description": description}, ensure_ascii=False),
                 kwargs.get("depends_on", "")),
            )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM task WHERE task_id=?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_first_task(self) -> Optional[dict]:
        """Get the first (most recent) task in the project."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM task ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def update_task(self, task_id: str, phase: Optional[str] = None,
                    status: Optional[str] = None, updated_at: str = "") -> None:
        """Update task phase/status in-place."""
        parts = []
        params = []
        if phase is not None:
            parts.append("phase = ?")
            params.append(phase)
        if status is not None:
            parts.append("status = ?")
            params.append(status)
        if updated_at:
            parts.append("updated_at = ?")
            params.append(updated_at)
        if not parts:
            return
        params.append(task_id)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE task SET {', '.join(parts)} WHERE task_id = ?", params)
            conn.commit()

    # ── Checkpoint ────────────────────────────────────

    def create_checkpoint(self, task_id: str, stage: str, status: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO checkpoint (task_id, stage, status) VALUES (?, ?, ?)",
                (task_id, stage, status),
            )
            conn.commit()

    def update_checkpoint(self, task_id: str, stage: str, status: str,
                          confirmed_at: str = "") -> None:
        with sqlite3.connect(self.db_path) as conn:
            if confirmed_at:
                conn.execute(
                    """UPDATE checkpoint SET status=?, confirmed_at=?
                       WHERE task_id=? AND stage=?""",
                    (status, confirmed_at, task_id, stage),
                )
            else:
                conn.execute(
                    "UPDATE checkpoint SET status=? WHERE task_id=? AND stage=?",
                    (status, task_id, stage),
                )
            conn.commit()

    # ── GateResult ───────────────────────────────────

    def insert_gate_result(self, task_id: str, gate_name: str,
                          passed: bool, detail: str = "") -> None:
        """Persist a gate check result for auditability (spec §5.2)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO gate_result (task_id, gate_name, passed, detail) VALUES (?, ?, ?, ?)",
                (task_id, gate_name, 1 if passed else 0, detail),
            )
            conn.commit()

    # ── Audit ─────────────────────────────────────────

    def write_audit(self, task_id: str, action: str, detail: str) -> None:
        prev_hash = self._last_audit_hash(task_id)
        combined = (prev_hash + action + detail).encode("utf-8")
        integrity = hashlib.sha256(combined).hexdigest()[:16]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (task_id, action, detail, integrity_hash) VALUES (?, ?, ?, ?)",
                (task_id, action, detail, integrity),
            )
            conn.commit()

    def _last_audit_hash(self, task_id: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT integrity_hash FROM audit_log WHERE task_id=? ORDER BY id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            return row[0] if row and row[0] else ""

    def verify_audit_integrity(self, task_id: str) -> dict:
        """Verify audit log chain integrity. Returns {valid: bool, broken_at: int|None}."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE task_id=? ORDER BY id",
                (task_id,),
            ).fetchall()
        prev_hash = ""
        for i, row in enumerate(rows):
            stored = row["integrity_hash"] or ""
            combined = (prev_hash + row["action"] + row["detail"]).encode("utf-8")
            expected = hashlib.sha256(combined).hexdigest()[:16]
            if stored and stored != expected:
                return {"valid": False, "broken_at": row["id"], "expected": expected, "stored": stored}
            prev_hash = stored
        return {"valid": True, "broken_at": None}

    def get_dependent_tasks(self, depends_on_id: str) -> list[dict]:
        """Get tasks that depend on the given task id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM task WHERE depends_on=? ORDER BY created_at",
                (depends_on_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_audit_logs(self, task_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE task_id=? ORDER BY created_at",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── ChangeLog ─────────────────────────────────────

    def insert_change_log(self, change: ChangeLog) -> None:
        """Insert a change log entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO change_log
                   (change_id, task_id, spec_ref, intent_group, summary, risk_label, diff_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (change.change_id, change.task_id, change.spec_ref,
                 change.intent_group.value, change.summary,
                 change.risk_label.value, change.diff_hash),
            )
            conn.commit()

    def get_change_logs(self, task_id: str) -> list[dict]:
        """Get all change logs for a task, ordered by creation time."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM change_log WHERE task_id=? ORDER BY created_at",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── ChangeEntry ───────────────────────────────────

    def insert_change_entry(self, entry: ChangeEntry) -> None:
        """Insert a change entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO change_entry
                   (entry_id, change_id, intent_group, agent_risk_label,
                    effective_risk_label, accuracy_score, file_path, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry.entry_id, entry.change_id, entry.intent_group.value,
                 entry.agent_risk_label.value, entry.effective_risk_label.value,
                 entry.accuracy_score, entry.file_path, entry.summary),
            )
            conn.commit()

    def get_change_entries(self, change_id: str) -> list[dict]:
        """Get all change entries for a change log."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM change_entry WHERE change_id=? ORDER BY created_at",
                (change_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_change_entry_accuracy(self, entry_id: str, accuracy: str,
                                     effective_risk: str) -> None:
        """Update accuracy metadata on a change entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE change_entry
                   SET accuracy_score=?, effective_risk_label=?
                   WHERE entry_id=?""",
                (accuracy, effective_risk, entry_id),
            )
            conn.commit()

    # ── DisagreementEvidence ──────────────────────────

    def insert_disagreement_evidence(self, entry_id: str,
                                     evidence: DisagreementEvidence) -> None:
        """Insert a disagreement evidence record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO disagreement_evidence
                   (entry_id, reviewer, severity, file_path, line_number,
                    agent_claim, reviewer_reason, diff_quote)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry_id, evidence.reviewer, evidence.severity,
                 evidence.file_path, evidence.line_number,
                 evidence.agent_claim, evidence.reviewer_reason,
                 evidence.diff_quote),
            )
            conn.commit()

    def get_disagreement_evidences(self, entry_id: str) -> list[dict]:
        """Get all disagreement evidences for a change entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM disagreement_evidence WHERE entry_id=? ORDER BY created_at",
                (entry_id,),
            ).fetchall()
            return [dict(r) for r in rows]
