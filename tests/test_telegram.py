from decimal import Decimal

from essentials.models import Token
from essentials.image_resolver import ResolvedImage
from essentials.telegram import ICON_ONLY_LABEL, TelegramClient, compact_usd, x_url


def token(**overrides):
    values = dict(
        address="CA/unsafe",
        symbol="DOGE2",
        name="Doge2 Caesar",
        market_cap=Decimal("87400"),
        total_fee=Decimal("6"),
        renowned_count=1,
        logo_url=None,
        twitter="https://x.com/user/status/123",
        has_social=True,
        launchpad_platform="Pump.fun",
        axiom_market_address=None,
    )
    values.update(overrides)
    return Token(**values)


def client(**emoji_ids):
    return TelegramClient("test", "1", 3, 5, 1, emoji_ids)


def test_compact_market_cap():
    assert compact_usd(Decimal("52100")) == "$52.1K"
    assert compact_usd(Decimal("187000")) == "$187K"
    assert compact_usd(Decimal("249800")) == "$249.8K"


def test_x_url_preserves_full_url_and_only_expands_bare_username():
    urls = [
        "https://x.com/user",
        "https://x.com/user/status/123",
        "https://x.com/i/communities/123",
        "https://twitter.com/user",
        "https://twitter.com/user/status/123",
    ]
    for url in urls:
        assert x_url(url) == url
    assert x_url("username") == "https://x.com/username"
    assert x_url("@username") == "https://x.com/username"
    assert x_url("username/status/123") == "https://x.com/username/status/123"
    assert x_url("i/communities/123") == "https://x.com/i/communities/123"
    assert x_url(None) is None
    assert x_url("not a link") is None


def test_caption_contains_full_html_escaped_ca_and_missing_x_fallback():
    tg = client()
    caption = tg.caption(token(address="CA<&>", twitter=None))
    assert "🪙 ca - <code>CA&lt;&amp;&gt;</code>" in caption
    assert "X̶" in caption


def test_keyboard_has_no_ca_button_and_hides_missing_axiom_market():
    tg = client()
    keyboard = tg.keyboard(token())
    assert len(keyboard["inline_keyboard"]) == 1
    buttons = keyboard["inline_keyboard"][0]
    assert all("copy_text" not in button for button in buttons)
    urls = [button["url"] for button in buttons]
    assert len(urls) == 2
    assert any("gmgn.ai" in url for url in urls)
    assert any("padre.gg" in url for url in urls)


def test_keyboard_has_exactly_three_icon_only_terminal_buttons():
    tg = client(axiom="111", gmgn="222", padre="333")
    keyboard = tg.keyboard(token(axiom_market_address="market"))
    buttons = keyboard["inline_keyboard"][0]
    assert len(buttons) == 3
    assert all(button["text"] == ICON_ONLY_LABEL for button in buttons)
    axiom = next(button for button in buttons if "axiom.trade" in button["url"])
    gmgn = next(button for button in buttons if "gmgn.ai" in button["url"])
    padre = next(button for button in buttons if "padre.gg" in button["url"])
    assert axiom["url"].endswith("/market")
    assert axiom["icon_custom_emoji_id"] == "111"
    assert gmgn["icon_custom_emoji_id"] == "222"
    assert padre["icon_custom_emoji_id"] == "333"


async def test_text_alert_is_sent_to_configured_topic():
    tg = client()
    calls = []

    async def fake_call(method, **kwargs):
        calls.append((method, kwargs))
        return {"message_id": 10}

    tg._call = fake_call
    try:
        assert await tg.send_token(token()) == 10
    finally:
        await tg.close()

    assert calls[0][0] == "sendMessage"
    assert calls[0][1]["json"]["message_thread_id"] == 3


async def test_photo_and_its_text_fallback_stay_in_same_topic():
    tg = client()
    calls = []

    async def fake_call(method, **kwargs):
        calls.append((method, kwargs))
        if method == "sendPhoto":
            from essentials.telegram import TelegramError
            raise TelegramError("bad photo")
        return {"message_id": 11}

    tg._call = fake_call
    try:
        image = ResolvedImage(b"image", "image/png", "logo.png", "gmgn")
        assert await tg.send_token(token(logo_url="https://example.com/logo.png"), image) == 11
    finally:
        await tg.close()

    assert calls[0][0] == "sendPhoto"
    assert calls[0][1]["data"]["message_thread_id"] == "3"
    assert calls[1][0] == "sendMessage"
    assert calls[1][1]["json"]["message_thread_id"] == 3


async def test_photo_alert_uses_send_photo_caption_keyboard_and_topic():
    tg = client(axiom="111", gmgn="222", padre="333")
    calls = []

    async def fake_call(method, **kwargs):
        calls.append((method, kwargs))
        return {"message_id": 12}

    tg._call = fake_call
    try:
        image = ResolvedImage(b"image", "image/png", "logo.png", "metadata")
        assert await tg.send_token(token(logo_url="https://example.com/logo.png"), image) == 12
    finally:
        await tg.close()

    assert len(calls) == 1
    assert calls[0][0] == "sendPhoto"
    assert calls[0][1]["data"]["message_thread_id"] == "3"
    assert "🪙 ca - <code>CA/unsafe</code>" in calls[0][1]["data"]["caption"]
    assert "reply_markup" in calls[0][1]["data"]
