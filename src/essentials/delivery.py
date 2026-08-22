from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .db import AlertStore
from .image_resolver import ResolvedImage
from .models import Token
from .telegram import TelegramClient


@dataclass(frozen=True)
class DeliveryResult:
    card_message_id: int
    data_message_id: int | None
    status: str


class AlertDelivery:
    """Serializes complete Telegram bundles and persists step-level progress."""

    def __init__(self, telegram: TelegramClient, store: AlertStore | None = None):
        self.telegram = telegram
        self.store = store
        self._lock = asyncio.Lock()

    async def send_alert_bundle(
        self,
        token: Token,
        image: ResolvedImage | None,
        second_message_content: str | None = None,
    ) -> DeliveryResult:
        async with self._lock:
            state = await self.store.get_delivery(token.address) if self.store else None
            if state and state.delivery_status == "completed":
                if state.card_message_id is None:
                    raise RuntimeError("Completed delivery has no card message ID")
                return DeliveryResult(
                    state.card_message_id, state.data_message_id, state.delivery_status
                )

            if self.store and state is None:
                await self.store.ensure_pending(
                    token.address,
                    self.telegram.chat_id,
                    self.telegram.alerts_thread_id,
                )

            card_message_id = state.card_message_id if state else None
            if card_message_id is None:
                card_message_id = await self.telegram.send_token(token, image)
                if card_message_id is None:
                    raise RuntimeError("Telegram card response has no message_id")
                if self.store:
                    await self.store.mark_card_sent(token.address, card_message_id)

            if second_message_content is None:
                if self.store:
                    await self.store.mark_completed(token.address, None)
                return DeliveryResult(card_message_id, None, "completed")

            data_message_id = await self.telegram.send_second_message(
                second_message_content, card_message_id
            )
            if data_message_id is None:
                raise RuntimeError("Telegram second-message response has no message_id")
            if self.store:
                await self.store.mark_completed(token.address, data_message_id)
            return DeliveryResult(card_message_id, data_message_id, "completed")
