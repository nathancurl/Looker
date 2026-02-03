"""SQLite-backed deduplication store."""

import sqlite3
from datetime import datetime, timezone


class StateStore:
    """Tracks seen job UIDs to prevent duplicate notifications."""

    def __init__(self, db_path: str = "seen_jobs.db"):
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_items (
                uid TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                source_group TEXT NOT NULL,
                url TEXT
            )
            """
        )
        self._conn.commit()

    def is_seen(self, uid: str) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM seen_items WHERE uid = ?", (uid,)
        )
        return cursor.fetchone() is not None

    def mark_seen(self, uid: str, source_group: str, url: str = "") -> None:
        """Mark a UID as seen. Idempotent via INSERT OR IGNORE."""
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_items (uid, first_seen_ts, source_group, url) VALUES (?, ?, ?, ?)",
            (uid, datetime.now(timezone.utc).isoformat(), source_group, url),
        )
        self._conn.commit()

    def count(self) -> int:
        cursor = self._conn.execute("SELECT COUNT(*) FROM seen_items")
        return cursor.fetchone()[0]

    def close(self) -> None:
        self._conn.close()
