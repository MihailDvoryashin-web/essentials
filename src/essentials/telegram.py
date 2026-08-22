from __future__ import annotations

import html
import logging
import re
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from .image_resolver import ResolvedImage
from .models import Token
from .retry import with_retry

_BARE_X = re.compile(r"^@?([A-Za-z0-9_]{1,15})$")
_RELATIVE_X = re.compile(r"^(?:[A-Za-z0-9_]{1,15}/status/[0-9]+|i/communities/[0-9]+)$")
ICON_ONLY_LABEL = "\u2063"
TICKER_WORD_JOINER = "\u2060"
logger = logging.getLogger(__name__)


class TelegramError(RuntimeError):
    pass


def compact_usd(value: Decimal) -> str:
    if value >= Decimal("1000000"):
        scaled, suffix = value / Decimal("1000000"), "M"
    elif value >= Decimal("1000"):
        scaled, suffix = value / Decimal("1000"), "K"
    else:
        scaled, suffix = value, ""
    rounded = scaled.quantize(Decimal("0.1"))
    rendered = f"{rounded:f}".rstrip("0").rstrip(".")
    return f"${rendered}{suffix}"


def x_url(value: str | None) -> str | None:
    if not value:
        return None
    match = _BARE_X.fullmatch(value)
    if match:
        return f"https://x.com/{match.group(1)}"
    if _RELATIVE_X.fullmatch(value):
        return f"https://x.com/{value}"
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    return None


class TelegramClient:
    def __init__(
        self,
        token: str,
        chat_id: str,
        alerts_thread_id: int | None,
        timeout_seconds: int,
        max_retries: int,
        emoji_ids: dict[str, str | None],
    ):
        self.chat_id = chat_id
        self.alerts_thread_id = alerts_thread_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.max_retries = max_retries
        self.emoji_ids = emoji_ids
        self.http = httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True)

    async def close(self) -> None:
        await self.http.aclose()

    def caption(self, token: Token) -> str:
        twitter = x_url(token.twitter)
        x_line = f'<a href="{html.escape(twitter, quote=True)}">X</a>' if twitter else "X̶"
        display_symbol = "$" + TICKER_WORD_JOINER + token.symbol.lstrip("$")
        return "\n".join([
            "🧠 <b>smarts detected</b>",
            "",
            f"{html.escape(display_symbol)} - {html.escape(token.name)} - {compact_usd(token.market_cap)}",
            "",
            x_line,
            "",
            f"🪙 ca - <code>{html.escape(token.address)}</code>",
            "",
            "⬇️ <b>holders distribution and info</b>",
        ])

    def keyboard(self, token: Token) -> dict[str, Any]:
        terminals: list[dict[str, Any]] = []
        urls = [
            ("Axiom", f"https://axiom.trade/meme/{quote(token.axiom_market_address, safe='')}" if token.axiom_market_address else None),
            ("GMGN", f"https://gmgn.ai/sol/token/{quote(token.address, safe='')}"),
            ("Padre", f"https://trade.padre.gg/trade/solana/{quote(token.address, safe='')}"),
        ]
        for name, url in urls:
            if not url:
                continue
            button: dict[str, Any] = {"text": ICON_ONLY_LABEL, "url": url}
            emoji_id = self.emoji_ids.get(name.lower())
            if emoji_id:
                button["icon_custom_emoji_id"] = emoji_id
            terminals.append(button)
        return {"inline_keyboard": [terminals]}

    async def send_token(self, token: Token, image: ResolvedImage | None = None) -> int | None:
        caption = self.caption(token)
        keyboard = self.keyboard(token)
        if image is not None:
            try:
                result = await self._call(
                    "sendPhoto",
                    data={
                        "chat_id": self.chat_id,
                        **({"message_thread_id": str(self.alerts_thread_id)} if self.alerts_thread_id is not None else {}),
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_markup": __import__("json").dumps(keyboard),
                    },
                    files={"photo": (image.filename, image.content, image.mime_type)},
                )
                return result.get("message_id")
            except TelegramError as exc:
                # A malformed/unsupported image must not suppress the alert.
                logger.warning("logo sendPhoto failed: %s", str(exc))
        result = await self._call("sendMessage", json={
            "chat_id": self.chat_id,
            **({"message_thread_id": self.alerts_thread_id} if self.alerts_thread_id is not None else {}),
            "text": caption,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
            "disable_web_page_preview": True,
        })
        return result.get("message_id")

    async def send_second_message(self, text: str, card_message_id: int) -> int | None:
        result = await self._call("sendMessage", json={
            "chat_id": self.chat_id,
            **({"message_thread_id": self.alerts_thread_id} if self.alerts_thread_id is not None else {}),
            "text": text,
            "reply_parameters": {"message_id": card_message_id},
        })
        return result.get("message_id")

    async def _call(self, method: str, **kwargs: Any) -> dict[str, Any]:
        async def request() -> dict[str, Any]:
            try:
                response = await self.http.post(f"{self.base_url}/{method}", **kwargs)
            except httpx.HTTPError as exc:
                raise TelegramError(f"Telegram transport error: {type(exc).__name__}") from exc
            if response.status_code >= 500 or response.status_code == 429:
                raise TelegramError(f"Telegram transient error: {response.status_code}")
            try:
                payload = response.json()
            except ValueError as exc:
                raise TelegramError("Telegram returned invalid JSON") from exc
            if not response.is_success or not payload.get("ok"):
                raise TelegramError(f"Telegram rejected {method}: {payload.get('description', response.status_code)}")
            return payload["result"]
        return await with_retry(request, attempts=self.max_retries)
