#!/usr/bin/env python3
"""Fetch one live GMGN candidate and send one production token card safely."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import shlex
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any

from essentials.config import Settings
from essentials.gmgn import GmgnError
from essentials.image_resolver import ImageResolver
from essentials.models import Token
from essentials.telegram import ICON_ONLY_LABEL, TelegramClient, x_url


def load_local_env() -> None:
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


def configured_emoji_ids(settings: Settings) -> dict[str, str]:
    values = {
        "axiom": settings.axiom_emoji_id,
        "gmgn": settings.gmgn_emoji_id,
        "padre": settings.padre_emoji_id,
    }
    missing = [f"{name.upper()}_EMOJI_ID" for name, value in values.items() if not value]
    if missing:
        raise ValueError("Missing live-test settings: " + ", ".join(missing))
    return {name: value for name, value in values.items() if value is not None}


def select_live_token(candidates: list[tuple[dict[str, Any], Token]]) -> tuple[dict[str, Any], Token] | None:
    return candidates[0] if candidates else None


def decimal_value(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def has_social(item: dict[str, Any]) -> bool:
    return Token.has_social_from_gmgn(item)


def kol_count(item: dict[str, Any]) -> int | None:
    try:
        return int(item.get("renowned_count", 0))
    except (TypeError, ValueError):
        return None


def socials_summary(item: dict[str, Any]) -> str:
    names = [
        name
        for name in ("twitter", "telegram", "website", "instagram", "tiktok")
        if isinstance(item.get(name), str) and item[name].strip()
    ]
    if names:
        return ",".join(names)
    return "yes" if has_social(item) else "none"


def gmgn_command(settings: Settings) -> list[str]:
    return [
        settings.gmgn_cli_bin, "market", "trenches",
        "--chain", "sol",
        "--type", "new_creation", "near_completion", "completed",
        "--launchpad-platform", "Pump.fun",
        "--limit", "80",
        "--raw",
    ]


def market_cap_fields(item: dict[str, Any]) -> list[str]:
    exact_names = {"mc", "mcp", "marketcap", "market_cap", "usd_market_cap"}
    return sorted(
        key
        for key in item
        if key.lower() in exact_names
        or ("market" in key.lower() and "cap" in key.lower())
    )


def print_raw_market_cap_diagnostics(rows: list[dict[str, Any]]) -> None:
    print("First 20 raw GMGN market-cap diagnostics:")
    print("symbol | raw market cap value | Python type | relevant raw field names")
    for item in rows[:20]:
        fields = market_cap_fields(item)
        values = {field: item.get(field) for field in fields}
        types = {field: type(item.get(field)).__name__ for field in fields}
        print(f"{item.get('symbol') or '?'} | {values} | {types} | {fields}")


async def fetch_raw_pump_rows(settings: Settings) -> list[dict[str, Any]]:
    command = gmgn_command(settings)
    print(f"GMGN CLI command: {shlex.join(command)}")
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise GmgnError(f"GMGN CLI not found: {settings.gmgn_cli_bin}") from exc
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=settings.gmgn_cli_timeout_seconds
        )
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise GmgnError("GMGN CLI timed out") from exc
    if process.returncode != 0:
        detail = stderr.decode(errors="replace").strip()[-1000:]
        raise GmgnError(f"GMGN CLI exited with {process.returncode}: {detail}")
    try:
        payload = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError as exc:
        raise GmgnError("GMGN CLI returned invalid JSON") from exc
    data = payload.get("data", payload) if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise GmgnError("GMGN response has no data object")
    rows: list[dict[str, Any]] = []
    for key in ("new_creation", "pump", "completed"):
        group = data.get(key, [])
        if isinstance(group, list):
            rows.extend(item for item in group if isinstance(item, dict))
    return rows


def diagnose_and_filter(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Token]]:
    print_raw_market_cap_diagnostics(rows)
    after_mc = [
        item for item in rows
        if (market_cap := Token.market_cap_from_gmgn(item)) is not None
        and Decimal("50000") <= market_cap <= Decimal("250000")
    ]
    after_social = [item for item in after_mc if has_social(item)]
    after_fees = [
        item for item in after_social
        if (fees := decimal_value(item.get("total_fee"))) is not None
        and fees >= Decimal("5")
    ]
    after_kol = [
        item for item in after_fees
        if (kol := kol_count(item)) is not None and kol >= 1
    ]

    print(f"GMGN rows total: {len(rows)}")
    print(f"After MC 50K–250K: {len(after_mc)}")
    print(f"After has_social: {len(after_social)}")
    print(f"After Total Fees >= 5 SOL: {len(after_fees)}")
    print(f"After KOL >= 1: {len(after_kol)}")
    print("First 10 after MC: symbol | market_cap | total_fees | renowned_count/KOL | socials")
    for item in after_mc[:10]:
        print(
            f"{item.get('symbol') or '?'} | "
            f"{item.get('market_cap')} | "
            f"{item.get('total_fee')} | "
            f"{item.get('renowned_count', 0)} | "
            f"{socials_summary(item)}"
        )

    candidates: list[tuple[dict[str, Any], Token]] = []
    for item in after_kol:
        token = Token.from_gmgn(item)
        if token is not None and token.passes_stage1():
            candidates.append((item, token))
    return candidates


def print_selected_mapping(raw: dict[str, Any], token: Token) -> None:
    print(f"symbol={token.symbol}")
    print(f"raw_logo={raw.get('logo')}")
    print(f"parsed_logo={token.logo_url}")
    print(f"logo_present={'yes' if token.logo_url else 'no'}")
    print(f"raw_twitter={raw.get('twitter')}")
    print(f"parsed_twitter={token.twitter}")
    print(f"normalized_twitter={x_url(token.twitter)}")


def verify_card(telegram: TelegramClient, token: Token) -> None:
    keyboard = telegram.keyboard(token)
    if len(keyboard["inline_keyboard"]) != 1:
        raise RuntimeError("Keyboard must contain only the terminal row")
    terminal_buttons = keyboard["inline_keyboard"][0]
    expected_count = 3 if token.axiom_market_address else 2
    if len(terminal_buttons) != expected_count:
        raise RuntimeError("Live token produced an unexpected number of terminal buttons")
    if any(button.get("text") != ICON_ONLY_LABEL for button in terminal_buttons):
        raise RuntimeError("Terminal buttons are not icon-only")
    if any(not button.get("icon_custom_emoji_id") for button in terminal_buttons):
        raise RuntimeError("A terminal button has no custom emoji ID")
    expected_hosts = ["gmgn.ai", "padre.gg"]
    if token.axiom_market_address:
        expected_hosts.insert(0, "axiom.trade")
    urls = [button["url"] for button in terminal_buttons]
    if any(not any(host in url for url in urls) for host in expected_hosts):
        raise RuntimeError("A required terminal URL is missing")
    caption = telegram.caption(token)
    escaped_ca = html.escape(token.address)
    if f"<code>{escaped_ca}</code>" not in caption:
        raise RuntimeError("Caption does not contain the full code-formatted token CA")
    twitter = x_url(token.twitter)
    if twitter:
        if html.escape(twitter, quote=True) not in caption:
            raise RuntimeError("Caption does not preserve the token X URL")
    elif "X̶" not in caption:
        raise RuntimeError("Caption does not contain the missing-X fallback")


async def send_live_alert() -> None:
    load_local_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings.from_env()
    if settings.telegram_alerts_thread_id is None:
        raise ValueError("Missing live-test setting: TELEGRAM_ALERTS_THREAD_ID")
    emoji_ids = configured_emoji_ids(settings)

    # One un-retried raw request enables sequential diagnostics without touching production filters.
    rows = await fetch_raw_pump_rows(settings)
    candidates = diagnose_and_filter(rows)
    selected = select_live_token(candidates)
    if selected is None:
        print("No current token passes the Stage 1 prefilter.")
        return
    raw_token, token = selected
    print_selected_mapping(raw_token, token)

    telegram = TelegramClient(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        settings.telegram_alerts_thread_id,
        settings.http_timeout_seconds,
        settings.max_retries,
        emoji_ids,
    )
    verify_card(telegram, token)
    image_resolver = ImageResolver(settings.solana_rpc_url, settings.http_timeout_seconds)

    try:
        image = await image_resolver.resolve(token)
        message_id = await telegram.send_token(token, image)
    finally:
        await telegram.close()
        await image_resolver.close()

    method = "sendPhoto" if image else "sendMessage"
    print(
        f"Live alert sent: message_id={message_id}, thread_id={settings.telegram_alerts_thread_id}, "
        f"method={method}, ca={token.address}, "
        f"image_source={image.source if image else 'fallback'}, "
        f"image_bytes={len(image.content) if image else 0}, "
        f"image_type={image.mime_type if image else 'none'}"
    )


if __name__ == "__main__":
    asyncio.run(send_live_alert())
