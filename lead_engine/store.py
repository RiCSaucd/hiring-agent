"""SQLite ledger for Nexus leads, accounts, batches, captures, and activity."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from lead_engine.seed import seed_accounts, seed_activity, seed_batches, seed_captures, seed_leads

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS captures (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity (
    id TEXT PRIMARY KEY,
    at REAL NOT NULL,
    payload TEXT NOT NULL
);
"""


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)


def _loads(raw: str) -> dict[str, Any]:
    return json.loads(raw)


class LeadStore:
    def __init__(self, db_path: str | Path, seed: bool = True):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        if seed:
            self._ensure_seed()

    def close(self) -> None:
        self._conn.close()

    def _ensure_seed(self) -> None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = 'seeded'").fetchone()
        if row:
            return
        leads = seed_leads()
        accounts = seed_accounts(leads)
        for lead in leads:
            self.upsert_lead(lead)
        for account in accounts:
            self.upsert_account(account)
        for batch in seed_batches():
            self.upsert_batch(batch)
        for capture in seed_captures():
            self.upsert_capture(capture)
        for item in seed_activity():
            self.add_activity(item, existing_id=item["id"])
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES ('seeded', ?)",
            (str(time.time()),),
        )
        self._conn.commit()

    def reset_demo(self) -> None:
        for table in ("leads", "accounts", "batches", "captures", "activity", "meta"):
            self._conn.execute(f"DELETE FROM {table}")
        self._conn.commit()
        self._ensure_seed()

    def list_leads(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT payload FROM leads").fetchall()
        leads = [_loads(row["payload"]) for row in rows]
        leads.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return leads

    def get_lead(self, lead_id: str) -> dict[str, Any]:
        row = self._conn.execute("SELECT payload FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not row:
            raise KeyError(f"Lead not found: {lead_id}")
        return _loads(row["payload"])

    def upsert_lead(self, lead: dict[str, Any]) -> dict[str, Any]:
        lead_id = lead.get("id") or uid("lead")
        lead["id"] = lead_id
        self._conn.execute(
            "INSERT INTO leads (id, payload) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
            (lead_id, _dumps(lead)),
        )
        self._conn.commit()
        return lead

    def delete_lead(self, lead_id: str) -> None:
        self._conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        self._conn.commit()

    def find_duplicate(self, email: str = "", full_name: str = "", company: str = "", place_id: str = "") -> dict[str, Any] | None:
        email_key = (email or "").strip().lower()
        name_key = (full_name or "").strip().lower()
        company_key = (company or "").strip().lower()
        place_key = (place_id or "").strip()
        for lead in self.list_leads():
            if email_key and (lead.get("email") or "").strip().lower() == email_key:
                return lead
            if place_key and lead.get("place_id") == place_key:
                return lead
            if name_key and company_key:
                if (lead.get("full_name") or "").strip().lower() == name_key and (
                    lead.get("company") or ""
                ).strip().lower() == company_key:
                    return lead
        return None

    def list_accounts(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT payload FROM accounts").fetchall()
        return [_loads(row["payload"]) for row in rows]

    def upsert_account(self, account: dict[str, Any]) -> dict[str, Any]:
        account_id = account.get("id") or uid("acct")
        account["id"] = account_id
        self._conn.execute(
            "INSERT INTO accounts (id, payload) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
            (account_id, _dumps(account)),
        )
        self._conn.commit()
        return account

    def find_account(self, name: str) -> dict[str, Any] | None:
        key = (name or "").strip().lower()
        if not key:
            return None
        for account in self.list_accounts():
            if account.get("name", "").lower() == key:
                return account
        return None

    def list_batches(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT payload FROM batches").fetchall()
        batches = [_loads(row["payload"]) for row in rows]
        batches.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return batches

    def upsert_batch(self, batch: dict[str, Any]) -> dict[str, Any]:
        batch_id = batch.get("id") or uid("batch")
        batch["id"] = batch_id
        self._conn.execute(
            "INSERT INTO batches (id, payload) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
            (batch_id, _dumps(batch)),
        )
        self._conn.commit()
        return batch

    def list_captures(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT payload FROM captures").fetchall()
        captures = [_loads(row["payload"]) for row in rows]
        captures.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return captures

    def upsert_capture(self, capture: dict[str, Any]) -> dict[str, Any]:
        capture_id = capture.get("id") or uid("cap")
        capture["id"] = capture_id
        self._conn.execute(
            "INSERT INTO captures (id, payload) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
            (capture_id, _dumps(capture)),
        )
        self._conn.commit()
        return capture

    def list_activity(self, limit: int = 40) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT payload FROM activity ORDER BY at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_loads(row["payload"]) for row in rows]

    def add_activity(self, item: dict[str, Any], existing_id: str | None = None) -> dict[str, Any]:
        activity_id = existing_id or item.get("id") or uid("act")
        at = item.get("at") or time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        payload = {**item, "id": activity_id, "at": at}
        stamp = time.time()
        self._conn.execute(
            "INSERT INTO activity (id, at, payload) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, at = excluded.at",
            (activity_id, stamp, _dumps(payload)),
        )
        self._conn.commit()
        return payload


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"
