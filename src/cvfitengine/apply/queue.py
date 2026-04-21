"""
Apply queue — SQLite-backed audit log for all application actions.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".cvfit" / "jobs.db"


class ApplyError(Exception):
    pass


class ApplyQueue:
    """Manages the apply_log table: enqueue, mark, and list applications."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        _ensure_table(conn)
        return conn

    def enqueue(self, job_id: str, job_title: str, company: str, method: str) -> None:
        """Add a job to the apply queue.

        Raises ApplyError if already successfully applied.
        """
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT status FROM apply_log WHERE job_id = ?", (job_id,)
            ).fetchone()

            if existing and existing["status"] == "applied":
                raise ApplyError(
                    f"Already applied to {job_title} at {company} (job_id={job_id})"
                )

            if existing:
                # Update existing record to pending
                conn.execute(
                    """UPDATE apply_log
                       SET status = 'pending', method = ?, queued_at = ?, error_message = NULL
                       WHERE job_id = ?""",
                    (method, datetime.utcnow().isoformat(), job_id),
                )
            else:
                conn.execute(
                    """INSERT INTO apply_log
                       (job_id, job_title, company, queued_at, method, status)
                       VALUES (?, ?, ?, ?, ?, 'pending')""",
                    (job_id, job_title, company, datetime.utcnow().isoformat(), method),
                )

    def mark_awaiting_confirm(
        self,
        job_id: str,
        cover_letter: str = "",
        screenshot_path: str = "",
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE apply_log
                   SET status = 'awaiting_confirm',
                       cover_letter_used = ?,
                       screenshot_path = ?
                   WHERE job_id = ?""",
                (cover_letter, screenshot_path, job_id),
            )

    def mark_applied(self, job_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE apply_log
                   SET status = 'applied', applied_at = ?
                   WHERE job_id = ?""",
                (datetime.utcnow().isoformat(), job_id),
            )

    def mark_failed(self, job_id: str, error: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE apply_log
                   SET status = 'failed', error_message = ?
                   WHERE job_id = ?""",
                (error, job_id),
            )

    def mark_skipped(self, job_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE apply_log SET status = 'skipped' WHERE job_id = ?",
                (job_id,),
            )

    def get(self, job_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM apply_log WHERE job_id = ?", (job_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_all(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM apply_log ORDER BY queued_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_pending(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM apply_log WHERE status IN ('pending','awaiting_confirm') "
                "ORDER BY queued_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apply_log (
            job_id TEXT PRIMARY KEY,
            job_title TEXT,
            company TEXT,
            queued_at TEXT,
            applied_at TEXT,
            method TEXT,
            status TEXT DEFAULT 'pending',
            cover_letter_used TEXT,
            screenshot_path TEXT,
            error_message TEXT
        )
    """)
    # Add screenshot_path column if upgrading from older schema
    try:
        conn.execute("ALTER TABLE apply_log ADD COLUMN screenshot_path TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
