"""Local SQLite tracker for the job-seeker desk."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    target_role TEXT NOT NULL DEFAULT '',
    target_location TEXT NOT NULL DEFAULT '',
    remote_only INTEGER NOT NULL DEFAULT 1,
    resume_json TEXT NOT NULL DEFAULT '{}',
    resume_text TEXT NOT NULL DEFAULT '',
    resume_filename TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    packet TEXT NOT NULL,
    fit TEXT NOT NULL,
    created_at REAL NOT NULL,
    applied_at REAL,
    notes TEXT NOT NULL DEFAULT ''
);
"""


class Tracker:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO profile (id, updated_at) VALUES (1, ?)",
            (time.time(),),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get_profile(self) -> dict[str, Any]:
        row = self._conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        resume = json.loads(row["resume_json"] or "{}")
        return {
            "target_role": row["target_role"],
            "target_location": row["target_location"],
            "remote_only": bool(row["remote_only"]),
            "resume": resume,
            "resume_filename": row["resume_filename"],
            "has_resume": bool(resume),
            "updated_at": row["updated_at"],
        }

    def save_resume(
        self,
        resume: dict[str, Any],
        resume_text: str,
        filename: str,
        target_role: str | None = None,
        target_location: str | None = None,
        remote_only: bool | None = None,
    ) -> dict[str, Any]:
        profile = self.get_profile()
        role = target_role if target_role is not None else profile["target_role"]
        location = target_location if target_location is not None else profile["target_location"]
        remote = profile["remote_only"] if remote_only is None else remote_only
        self._conn.execute(
            """
            UPDATE profile
            SET resume_json = ?, resume_text = ?, resume_filename = ?,
                target_role = ?, target_location = ?, remote_only = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                json.dumps(resume),
                resume_text,
                filename,
                role,
                location,
                1 if remote else 0,
                time.time(),
            ),
        )
        self._conn.commit()
        return self.get_profile()

    def update_preferences(
        self,
        target_role: str | None = None,
        target_location: str | None = None,
        remote_only: bool | None = None,
    ) -> dict[str, Any]:
        profile = self.get_profile()
        role = target_role if target_role is not None else profile["target_role"]
        location = target_location if target_location is not None else profile["target_location"]
        remote = profile["remote_only"] if remote_only is None else remote_only
        self._conn.execute(
            """
            UPDATE profile
            SET target_role = ?, target_location = ?, remote_only = ?, updated_at = ?
            WHERE id = 1
            """,
            (role, location, 1 if remote else 0, time.time()),
        )
        self._conn.commit()
        return self.get_profile()

    def upsert_job(self, job: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO jobs (id, payload) VALUES (?, ?)",
            (job["id"], json.dumps(job)),
        )
        self._conn.commit()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT payload FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_jobs(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT payload FROM jobs").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def create_application(self, job_id: str, packet: dict[str, Any], fit: dict[str, Any]) -> dict[str, Any]:
        existing = self._conn.execute(
            "SELECT id FROM applications WHERE job_id = ? AND status != 'withdrawn' ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        now = time.time()
        if existing:
            self._conn.execute(
                "UPDATE applications SET packet = ?, fit = ?, status = 'draft', created_at = ? WHERE id = ?",
                (json.dumps(packet), json.dumps(fit), now, existing["id"]),
            )
            self._conn.commit()
            return self.get_application(int(existing["id"]))
        cursor = self._conn.execute(
            """
            INSERT INTO applications (job_id, status, packet, fit, created_at)
            VALUES (?, 'draft', ?, ?, ?)
            """,
            (job_id, json.dumps(packet), json.dumps(fit), now),
        )
        self._conn.commit()
        return self.get_application(int(cursor.lastrowid))

    def mark_applied(self, application_id: int, confirm: bool, notes: str = "") -> dict[str, Any]:
        if not confirm:
            raise ValueError("Refusing to mark applied without confirm=true")
        row = self.get_application(application_id)
        if not row:
            raise KeyError(f"Application {application_id} not found")
        self._conn.execute(
            "UPDATE applications SET status = 'applied', applied_at = ?, notes = ? WHERE id = ?",
            (time.time(), notes, application_id),
        )
        self._conn.commit()
        return self.get_application(application_id)

    def get_application(self, application_id: int) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        return self._row_to_application(row) if row else None

    def list_applications(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM applications ORDER BY created_at DESC").fetchall()
        return [self._row_to_application(row) for row in rows]

    def _row_to_application(self, row: sqlite3.Row) -> dict[str, Any]:
        job = self.get_job(row["job_id"]) or {"id": row["job_id"]}
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "status": row["status"],
            "packet": json.loads(row["packet"]),
            "fit": json.loads(row["fit"]),
            "created_at": row["created_at"],
            "applied_at": row["applied_at"],
            "notes": row["notes"],
            "job": job,
        }
