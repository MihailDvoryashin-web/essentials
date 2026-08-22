#!/usr/bin/env python3
"""Send two concurrent live bundles without polling or persistent delivery state."""

from __future__ import annotations

import asyncio
import logging

from essentials.config import Settings
from essentials.delivery import AlertDelivery
from essentials.image_resolver import ImageResolver
from essentials.telegram import TelegramClient

from test_live_alert import (
    configured_emoji_ids,
    diagnose_and_filter,
    fetch_raw_pump_rows,
    load_local_env,
    select_live_tokens,
    verify_card,
)

SECOND_MESSAGE = "📊 Essentials second message test"


async def main() -> None:
    load_local_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings.from_env()
    if settings.telegram_alerts_thread_id is None:
        raise ValueError("Missing live-test setting: TELEGRAM_ALERTS_THREAD_ID")

    # Exactly one GMGN fetch; no polling and no SQLite store is constructed.
    rows = await fetch_raw_pump_rows(settings)
    selected = select_live_tokens(diagnose_and_filter(rows), limit=2)
    if len(selected) < 2:
        print(f"Need two distinct live candidates; currently available: {len(selected)}")
        return

    telegram = TelegramClient(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        settings.telegram_alerts_thread_id,
        settings.http_timeout_seconds,
        settings.max_retries,
        configured_emoji_ids(settings),
    )
    resolver = ImageResolver(settings.solana_rpc_url, settings.http_timeout_seconds)
    delivery = AlertDelivery(telegram, store=None)

    async def send_one(raw_and_token):
        _, token = raw_and_token
        verify_card(telegram, token)
        image = await resolver.resolve(token)
        result = await delivery.send_alert_bundle(token, image, SECOND_MESSAGE)
        print(
            f"{token.symbol}: card_message_id={result.card_message_id}, "
            f"data_message_id={result.data_message_id}, status={result.status}"
        )

    try:
        await asyncio.gather(*(send_one(item) for item in selected))
    finally:
        await telegram.close()
        await resolver.close()


if __name__ == "__main__":
    asyncio.run(main())
