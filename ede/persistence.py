"""SQLite persistence layer.

Manages DB initialization, migrations, and CRUD for all entities.
All mutations write to disk immediately.
"""

import sqlite3
import pathlib
from typing import Optional

from ede.models import DDL_CREATE_TABLES, ChangeLog, IntentGroup, RiskLabel


class Persistence:
    """SQLite-backed persistence for EDE state."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def init_db(self) -> None:
        """Create database file and run schema DDL."""
        pathlib.Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(DDL_CREATE_TABLES)
            conn.commit()

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

    def create_task(self, task_id: str, project_id: str, description: str = "") -> None:
        """Create a new task in SPEC/PENDING state."""
        import json
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO task (task_id, project_id, phase, status, stage_data)
                   VALUES (?, ?, 'spec', 'pending', ?)""",
                (task_id, project_id, json.dumps({"description": description}, ensure_ascii=False)),
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

    # ── Audit ─────────────────────────────────────────

    def write_audit(self, task_id: str, action: str, detail: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (task_id, action, detail) VALUES (?, ?, ?)",
                (task_id, action, detail),
            )
            conn.commit()

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
