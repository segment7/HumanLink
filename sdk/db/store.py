"""
SQLite Storage for HumanLink SDK

Handles local storage of nonces, sessions, and audit logs
"""
import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path


logger = logging.getLogger(__name__)


class HumanLinkStore:
    """SQLite storage for HumanLink SDK"""

    def __init__(self, db_path: str = "~/.humanlink/storage.db"):
        """
        Initialize storage

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Device information
                CREATE TABLE IF NOT EXISTS devices (
                    did TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    attestation TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                );

                -- Nonce tracking for anti-replay protection
                CREATE TABLE IF NOT EXISTS nonces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_did TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    used_at TEXT NOT NULL,
                    assertion_id TEXT,
                    UNIQUE(device_did, nonce),
                    FOREIGN KEY(device_did) REFERENCES devices(did)
                );

                -- Session logs
                CREATE TABLE IF NOT EXISTS session_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    device_did TEXT NOT NULL,
                    action TEXT NOT NULL,
                    params TEXT NOT NULL,
                    assertion_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT
                );

                -- Audit records
                CREATE TABLE IF NOT EXISTS audit_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assertion_id TEXT UNIQUE NOT NULL,
                    device_did TEXT NOT NULL,
                    action TEXT NOT NULL,
                    params TEXT NOT NULL,
                    match_score INTEGER NOT NULL,
                    chain_checked BOOLEAN DEFAULT 0,
                    chain_check_reason TEXT,
                    created_at TEXT NOT NULL,
                    signature TEXT NOT NULL
                );

                -- Revoked assertions
                CREATE TABLE IF NOT EXISTS revoked_assertions (
                    assertion_id TEXT PRIMARY KEY,
                    revoked_at TEXT NOT NULL,
                    reason TEXT
                );

                -- Create indexes for performance
                CREATE INDEX IF NOT EXISTS idx_nonces_device_did ON nonces(device_did);
                CREATE INDEX IF NOT EXISTS idx_nonces_used_at ON nonces(used_at);
                CREATE INDEX IF NOT EXISTS idx_session_logs_device_did ON session_logs(device_did);
                CREATE INDEX IF NOT EXISTS idx_session_logs_created_at ON session_logs(created_at);
                CREATE INDEX IF NOT EXISTS idx_audit_device_did ON audit_records(device_did);
                CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_records(created_at);
            """)

    def store_device(self, did: str, public_key: str, attestation: Dict[str, Any]) -> bool:
        """
        Store device information

        Args:
            did: Device DID
            public_key: Device public key
            attestation: Device attestation info

        Returns:
            True if stored successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO devices (did, public_key, attestation, registered_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    did,
                    public_key,
                    json.dumps(attestation),
                    datetime.now(timezone.utc).isoformat()
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to store device: {e}")
            return False

    def get_device(self, did: str) -> Optional[Dict[str, Any]]:
        """
        Get device information

        Args:
            did: Device DID

        Returns:
            Device information or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT did, public_key, attestation, registered_at, is_active
                    FROM devices WHERE did = ?
                """, (did,))
                row = cursor.fetchone()

                if row:
                    return {
                        "did": row[0],
                        "public_key": row[1],
                        "attestation": json.loads(row[2]),
                        "registered_at": row[3],
                        "is_active": bool(row[4])
                    }
        except Exception as e:
            logger.error(f"Failed to get device: {e}")

        return None

    def check_nonce(self, device_did: str, nonce: str) -> bool:
        """
        Check if nonce has been used

        Args:
            device_did: Device DID
            nonce: Nonce to check

        Returns:
            True if nonce is fresh (not used)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM nonces WHERE device_did = ? AND nonce = ?
                """, (device_did, nonce))
                count = cursor.fetchone()[0]
                return count == 0
        except Exception as e:
            logger.error(f"Failed to check nonce: {e}")
            return False

    def mark_nonce_used(self, device_did: str, nonce: str, assertion_id: str) -> bool:
        """
        Mark nonce as used

        Args:
            device_did: Device DID
            nonce: Nonce value
            assertion_id: Associated assertion ID

        Returns:
            True if marked successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO nonces (device_did, nonce, used_at, assertion_id)
                    VALUES (?, ?, ?, ?)
                """, (
                    device_did,
                    nonce,
                    datetime.now(timezone.utc).isoformat(),
                    assertion_id
                ))
            return True
        except sqlite3.IntegrityError:
            # Nonce already used
            logger.warning(f"Nonce {nonce} already used for device {device_did}")
            return False
        except Exception as e:
            logger.error(f"Failed to mark nonce as used: {e}")
            return False

    def create_session_log(self, session_id: str, device_did: str, action: str,
                          params: Dict[str, Any]) -> bool:
        """
        Create session log entry

        Args:
            session_id: Session ID
            device_did: Device DID
            action: Action being performed
            params: Action parameters

        Returns:
            True if created successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO session_logs (session_id, device_did, action, params, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    device_did,
                    action,
                    json.dumps(params),
                    "started",
                    datetime.now(timezone.utc).isoformat()
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to create session log: {e}")
            return False

    def update_session_log(self, session_id: str, status: str, assertion_id: Optional[str] = None,
                          error_message: Optional[str] = None) -> bool:
        """
        Update session log

        Args:
            session_id: Session ID
            status: New status
            assertion_id: Associated assertion ID
            error_message: Error message if failed

        Returns:
            True if updated successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE session_logs
                    SET status = ?, assertion_id = ?, completed_at = ?, error_message = ?
                    WHERE session_id = ?
                """, (
                    status,
                    assertion_id,
                    datetime.now(timezone.utc).isoformat(),
                    error_message,
                    session_id
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to update session log: {e}")
            return False

    def store_audit_record(self, assertion_id: str, device_did: str, action: str,
                          params: Dict[str, Any], match_score: int, chain_checked: bool,
                          chain_check_reason: Optional[str], signature: str) -> bool:
        """
        Store audit record

        Args:
            assertion_id: Assertion ID
            device_did: Device DID
            action: Action performed
            params: Action parameters
            match_score: Biometric match score
            chain_checked: Whether chain verification was performed
            chain_check_reason: Reason if chain check was skipped
            signature: Device signature

        Returns:
            True if stored successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO audit_records
                    (assertion_id, device_did, action, params, match_score, chain_checked,
                     chain_check_reason, created_at, signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    assertion_id,
                    device_did,
                    action,
                    json.dumps(params),
                    match_score,
                    chain_checked,
                    chain_check_reason,
                    datetime.now(timezone.utc).isoformat(),
                    signature
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to store audit record: {e}")
            return False

    def revoke_assertion(self, assertion_id: str, reason: str = "revoked") -> bool:
        """
        Mark assertion as revoked

        Args:
            assertion_id: Assertion ID to revoke
            reason: Revocation reason

        Returns:
            True if revoked successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO revoked_assertions (assertion_id, revoked_at, reason)
                    VALUES (?, ?, ?)
                """, (
                    assertion_id,
                    datetime.now(timezone.utc).isoformat(),
                    reason
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to revoke assertion: {e}")
            return False

    def is_assertion_revoked(self, assertion_id: str) -> bool:
        """
        Check if assertion is revoked

        Args:
            assertion_id: Assertion ID to check

        Returns:
            True if revoked
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM revoked_assertions WHERE assertion_id = ?
                """, (assertion_id,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(f"Failed to check assertion revocation: {e}")
            return False

    def cleanup_old_nonces(self, days: int = 30) -> int:
        """
        Clean up old nonces

        Args:
            days: Remove nonces older than this many days

        Returns:
            Number of nonces removed
        """
        try:
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
            cutoff_str = cutoff_date.isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM nonces WHERE used_at < ?
                """, (cutoff_str,))
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to cleanup old nonces: {e}")
            return 0

    def get_audit_records(self, device_did: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit records

        Args:
            device_did: Filter by device DID (optional)
            limit: Maximum number of records

        Returns:
            List of audit records
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if device_did:
                    cursor = conn.execute("""
                        SELECT assertion_id, device_did, action, params, match_score,
                               chain_checked, chain_check_reason, created_at, signature
                        FROM audit_records WHERE device_did = ?
                        ORDER BY created_at DESC LIMIT ?
                    """, (device_did, limit))
                else:
                    cursor = conn.execute("""
                        SELECT assertion_id, device_did, action, params, match_score,
                               chain_checked, chain_check_reason, created_at, signature
                        FROM audit_records
                        ORDER BY created_at DESC LIMIT ?
                    """, (limit,))

                records = []
                for row in cursor.fetchall():
                    records.append({
                        "assertion_id": row[0],
                        "device_did": row[1],
                        "action": row[2],
                        "params": json.loads(row[3]),
                        "match_score": row[4],
                        "chain_checked": bool(row[5]),
                        "chain_check_reason": row[6],
                        "created_at": row[7],
                        "signature": row[8]
                    })
                return records
        except Exception as e:
            logger.error(f"Failed to get audit records: {e}")
            return []

    def close(self):
        """Close database connections"""
        # SQLite connections are automatically closed when exiting context manager
        pass