from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryState:
    token_ca: str
    card_message_id: int | None
    data_message_id: int | None
    telegram_chat_id: str
    telegram_thread_id: int | None
    delivery_status: str


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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_deliveries (
                    token_ca TEXT PRIMARY KEY,
                    card_message_id INTEGER,
                    data_message_id INTEGER,
                    telegram_chat_id TEXT NOT NULL,
                    telegram_thread_id INTEGER,
                    delivery_status TEXT NOT NULL CHECK (
                        delivery_status IN ('pending', 'card_sent', 'completed')
                    ),
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO alert_deliveries(
                    token_ca, card_message_id, data_message_id,
                    telegram_chat_id, telegram_thread_id, delivery_status, updated_at
                )
                SELECT ca, telegram_message_id, NULL, '', NULL, 'completed', alerted_at
                FROM alerted_tokens
                """
            )

    async def contains(self, ca: str) -> bool:
        return await asyncio.to_thread(self._contains, ca)

    def _contains(self, ca: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM alert_deliveries WHERE token_ca = ? AND delivery_status = 'completed'",
                (ca,),
            ).fetchone()
        return row is not None

    async def get_delivery(self, ca: str) -> DeliveryState | None:
        return await asyncio.to_thread(self._get_delivery, ca)

    def _get_delivery(self, ca: str) -> DeliveryState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT token_ca, card_message_id, data_message_id, telegram_chat_id,
                       telegram_thread_id, delivery_status
                FROM alert_deliveries WHERE token_ca = ?
                """,
                (ca,),
            ).fetchone()
        return DeliveryState(*row) if row else None

    async def ensure_pending(self, ca: str, chat_id: str, thread_id: int | None) -> None:
        await asyncio.to_thread(self._ensure_pending, ca, chat_id, thread_id)

    def _ensure_pending(self, ca: str, chat_id: str, thread_id: int | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO alert_deliveries(
                    token_ca, card_message_id, data_message_id,
                    telegram_chat_id, telegram_thread_id, delivery_status, updated_at
                ) VALUES (?, NULL, NULL, ?, ?, 'pending', ?)
                """,
                (ca, chat_id, thread_id, datetime.now(timezone.utc).isoformat()),
            )

    async def mark_card_sent(self, ca: str, message_id: int) -> None:
        await asyncio.to_thread(self._mark_card_sent, ca, message_id)

    def _mark_card_sent(self, ca: str, message_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE alert_deliveries
                SET card_message_id = ?, delivery_status = 'card_sent', updated_at = ?
                WHERE token_ca = ? AND delivery_status = 'pending'
                """,
                (message_id, datetime.now(timezone.utc).isoformat(), ca),
            )

    async def mark_completed(self, ca: str, data_message_id: int | None) -> None:
        await asyncio.to_thread(self._mark_completed, ca, data_message_id)

    def _mark_completed(self, ca: str, data_message_id: int | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE alert_deliveries
                SET data_message_id = ?, delivery_status = 'completed', updated_at = ?
                WHERE token_ca = ? AND delivery_status = 'card_sent'
                """,
                (data_message_id, datetime.now(timezone.utc).isoformat(), ca),
            )

    async def record(self, ca: str, message_id: int | None) -> None:
        await asyncio.to_thread(self._record, ca, message_id)

    def _record(self, ca: str, message_id: int | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO alerted_tokens(ca, alerted_at, telegram_message_id) VALUES (?, ?, ?)",
                (ca, datetime.now(timezone.utc).isoformat(), message_id),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO alert_deliveries(
                    token_ca, card_message_id, data_message_id,
                    telegram_chat_id, telegram_thread_id, delivery_status, updated_at
                ) VALUES (?, ?, NULL, '', NULL, 'completed', ?)
                """,
                (ca, message_id, datetime.now(timezone.utc).isoformat()),
            )
