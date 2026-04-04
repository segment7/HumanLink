from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class SQLiteStore:
    def __init__(self, path: str):
        self.path = os.path.expanduser(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS used_nonces (
                device_did TEXT NOT NULL,
                nonce TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (device_did, nonce)
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT NOT NULL,
                command TEXT,
                context_json TEXT,
                challenge_nonce TEXT,
                assertion_id TEXT,
                device_did TEXT,
                valid INTEGER NOT NULL,
                failure_step INTEGER,
                failure_reason TEXT,
                chain_checked INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def nonce_exists(self, device_did: str, nonce: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM used_nonces WHERE device_did = ? AND nonce = ?",
            (device_did, nonce),
        ).fetchone()
        return row is not None

    def record_nonce(self, device_did: str, nonce: str, created_at: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO used_nonces(device_did, nonce, created_at) VALUES (?, ?, ?)",
            (device_did, nonce, created_at),
        )
        self.conn.commit()

    def write_audit(
        self,
        *,
        logged_at: str,
        command: Optional[str],
        context: Optional[Dict[str, Any]],
        challenge_nonce: str,
        assertion_id: str,
        device_did: str,
        valid: bool,
        failure_step: Optional[int],
        failure_reason: Optional[str],
        chain_checked: bool,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO audit_log(
                logged_at, command, context_json, challenge_nonce, assertion_id,
                device_did, valid, failure_step, failure_reason, chain_checked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                logged_at,
                command,
                json.dumps(context, sort_keys=True) if context is not None else None,
                challenge_nonce,
                assertion_id,
                device_did,
                int(valid),
                failure_step,
                failure_reason,
                int(chain_checked),
            ),
        )
        self.conn.commit()

    def set_device_did(self, device_did: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO kv_store(key, value) VALUES ('device_did', ?)",
            (device_did,),
        )
        self.conn.commit()

    def get_device_did(self) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM kv_store WHERE key = 'device_did'").fetchone()
        return None if row is None else row["value"]
