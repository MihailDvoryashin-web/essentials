#!/usr/bin/env python3
"""Send exactly one Telegram token-card alert without querying GMGN."""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from pathlib import Path

from essentials.models import Token
from essentials.image_resolver import ImageResolver
from essentials.telegram import ICON_ONLY_LABEL, TelegramClient


def load_local_env() -> None:
    """Load simple KEY=VALUE entries from the project .env without overriding exports."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing test-alert setting: {name}")
    return value


async def send_test_alert() -> None:
    load_local_env()
    bot_token = required("TELEGRAM_BOT_TOKEN")
    chat_id = required("TELEGRAM_CHAT_ID")
    thread_id = int(required("TELEGRAM_ALERTS_THREAD_ID"))
    emoji_ids = {
        "axiom": required("AXIOM_EMOJI_ID"),
        "gmgn": required("GMGN_EMOJI_ID"),
        "padre": required("PADRE_EMOJI_ID"),
    }

    # Wrapped SOL is a valid Solana mint used here only to exercise the card and terminal buttons.
    test_ca = "So11111111111111111111111111111111111111112"
    token = Token(
        address=test_ca,
        symbol="TEST",
        name="Essentials Test",
        market_cap=Decimal("100000"),
        total_fee=Decimal("5"),
        renowned_count=1,
        logo_url="https://telegram.org/img/t_logo.png",
        twitter=None,
        has_social=True,
        launchpad_platform="Pump.fun",
        axiom_market_address=test_ca,
    )
    telegram = TelegramClient(
        bot_token,
        chat_id,
        thread_id,
        int(os.getenv("HTTP_TIMEOUT_SECONDS", "15")),
        int(os.getenv("MAX_RETRIES", "3")),
        emoji_ids,
    )
    image_resolver = ImageResolver(
        os.getenv("SOLANA_RPC_URL", "").strip() or "https://api.mainnet-beta.solana.com",
        int(os.getenv("HTTP_TIMEOUT_SECONDS", "15")),
    )
    terminal_buttons = telegram.keyboard(token)["inline_keyboard"][1]
    if len(terminal_buttons) != 3:
        raise RuntimeError("Expected exactly three terminal buttons")
    if any(button.get("text") != ICON_ONLY_LABEL for button in terminal_buttons):
        raise RuntimeError("Terminal buttons are not icon-only")
    if any(not button.get("icon_custom_emoji_id") for button in terminal_buttons):
        raise RuntimeError("A terminal button has no custom emoji ID")
    try:
        image = await image_resolver.resolve(token)
        message_id = await telegram.send_token(token, image)
    finally:
        await telegram.close()
        await image_resolver.close()
    print(f"Test alert sent: message_id={message_id}, thread_id={thread_id}")


if __name__ == "__main__":
    asyncio.run(send_test_alert())
