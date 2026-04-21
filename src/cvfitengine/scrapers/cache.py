"""
SQLite-backed job cache.
Stores JobListing records at ~/.cvfit/jobs.db with 24-hour TTL.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".cvfit" / "jobs.db"
TTL_HOURS = 24


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            salary_raw TEXT,
            employment_type TEXT,
            description_full TEXT,
            url TEXT,
            apply_url TEXT,
            source TEXT,
            easy_apply INTEGER DEFAULT 0,
            posted_date TEXT,
            scraped_at TEXT,
            fit_score REAL,
            skill_gaps TEXT,
            apply_status TEXT DEFAULT 'none'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cover_letter_cache (
            job_id TEXT PRIMARY KEY,
            cover_letter TEXT,
            created_at TEXT
        )
    """)
    conn.commit()


class JobCache:
    """Persistent SQLite cache for JobListing objects."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        _ensure_tables(conn)
        return conn

    def save(self, job: dict) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jobs
                (id, title, company, location, salary_raw, employment_type,
                 description_full, url, apply_url, source, easy_apply,
                 posted_date, scraped_at, fit_score, skill_gaps, apply_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                job.get("id", ""),
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("salary_raw", job.get("salary", "")),
                job.get("employment_type", job.get("type", "")),
                job.get("description_full", job.get("summary", "")),
                job.get("url", ""),
                job.get("apply_url", job.get("url", "")),
                job.get("source", ""),
                1 if job.get("easy_apply") else 0,
                job.get("posted_date", job.get("posted", "")),
                job.get("scraped_at", datetime.utcnow().isoformat()),
                job.get("fit_score"),
                json.dumps(job.get("skill_gaps") or []),
                job.get("apply_status", "none"),
            ))

    def get(self, job_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)

    def exists_fresh(self, job_id: str) -> bool:
        """Return True if job exists and was scraped within TTL_HOURS."""
        job = self.get(job_id)
        if not job:
            return False
        scraped_at = job.get("scraped_at", "")
        if not scraped_at:
            return False
        try:
            ts = datetime.fromisoformat(scraped_at)
            return datetime.utcnow() - ts < timedelta(hours=TTL_HOURS)
        except ValueError:
            return False

    def list_recent(self, hours: int = TTL_HOURS) -> list[dict]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE scraped_at >= ? ORDER BY scraped_at DESC",
                (cutoff,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def list_ranked(
        self,
        min_score: float = 0.0,
        limit: int = 50,
        source: Optional[str] = None,
    ) -> list[dict]:
        query = "SELECT * FROM jobs WHERE fit_score IS NOT NULL AND fit_score >= ?"
        params: list = [min_score]
        if source:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY fit_score DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update_status(self, job_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET apply_status = ? WHERE id = ?",
                (status, job_id)
            )

    def update_score(
        self,
        job_id: str,
        fit_score: float,
        skill_gaps: list[str],
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET fit_score = ?, skill_gaps = ? WHERE id = ?",
                (fit_score, json.dumps(skill_gaps), job_id)
            )

    def save_cover_letter(self, job_id: str, cover_letter: str) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cover_letter_cache (job_id, cover_letter, created_at)
                VALUES (?, ?, ?)
            """, (job_id, cover_letter, datetime.utcnow().isoformat()))

    def get_cover_letter(self, job_id: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT cover_letter FROM cover_letter_cache WHERE job_id = ?",
                (job_id,)
            ).fetchone()
        return row["cover_letter"] if row else None


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["easy_apply"] = bool(d.get("easy_apply", 0))
    raw_gaps = d.get("skill_gaps", "[]") or "[]"
    try:
        d["skill_gaps"] = json.loads(raw_gaps)
    except (json.JSONDecodeError, TypeError):
        d["skill_gaps"] = []
    # Backward-compat aliases for frontend
    d["salary"] = d.get("salary_raw", "")
    d["summary"] = (d.get("description_full") or "")[:280]
    d["posted"] = d.get("posted_date", "")
    d["type"] = d.get("employment_type", "")
    return d
