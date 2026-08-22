from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class AlertStore:
    def __init__(self, path: Path):
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alerted_tokens (
                    ca TEXT PRIMARY KEY,
                    alerted_at TEXT NOT NULL,
                    telegram_message_id INTEGER
                )
                """
            )

    async def contains(self, ca: str) -> bool:
        return await asyncio.to_thread(self._contains, ca)

    def _contains(self, ca: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM alerted_tokens WHERE ca = ?", (ca,)).fetchone()
        return row is not None

    async def record(self, ca: str, message_id: int | None) -> None:
        await asyncio.to_thread(self._record, ca, message_id)

    def _record(self, ca: str, message_id: int | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO alerted_tokens(ca, alerted_at, telegram_message_id) VALUES (?, ?, ?)",
                (ca, datetime.now(timezone.utc).isoformat(), message_id),
            )

