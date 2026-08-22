from __future__ import annotations

import asyncio
import logging

from .config import Settings
from .db import AlertStore
from .delivery import AlertDelivery
from .gmgn import GmgnClient
from .image_resolver import ImageResolver
from .service import AlertService
from .telegram import TelegramClient


async def async_main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx logs full request URLs; Telegram Bot API URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    store = AlertStore(settings.database_path)
    telegram = TelegramClient(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        settings.telegram_alerts_thread_id,
        settings.http_timeout_seconds,
        settings.max_retries,
        {
            "axiom": settings.axiom_emoji_id,
            "gmgn": settings.gmgn_emoji_id,
            "padre": settings.padre_emoji_id,
        },
    )
    image_resolver = ImageResolver(settings.solana_rpc_url, settings.http_timeout_seconds)
    service = AlertService(
        GmgnClient(settings.gmgn_cli_bin, settings.gmgn_cli_timeout_seconds, settings.max_retries),
        AlertDelivery(telegram, store),
        store,
        settings.poll_interval_seconds,
        image_resolver,
    )
    try:
        await service.run_forever()
    finally:
        await telegram.close()
        await image_resolver.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
