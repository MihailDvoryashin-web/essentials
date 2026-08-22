import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from essentials.db import AlertStore
from essentials.delivery import AlertDelivery
from essentials.models import Token


def token(ca: str, symbol: str) -> Token:
    return Token(
        address=ca,
        symbol=symbol,
        name=symbol,
        market_cap=Decimal("100000"),
        total_fee=Decimal("5"),
        renowned_count=1,
        logo_url=None,
        twitter=None,
        has_social=True,
        launchpad_platform="Pump.fun",
        axiom_market_address=None,
    )


class FakeTelegram:
    chat_id = "-100123"
    alerts_thread_id = 3

    def __init__(self):
        self.calls = []
        self.next_id = 100
        self.fail_card = False
        self.fail_second_once = False

    async def send_token(self, item, image):
        self.calls.append((item.symbol, "card"))
        await asyncio.sleep(0)
        if self.fail_card:
            raise RuntimeError("card failed")
        self.next_id += 1
        return self.next_id

    async def send_second_message(self, text, card_message_id):
        symbol = text.split(":", 1)[0]
        self.calls.append((symbol, "second", card_message_id))
        await asyncio.sleep(0)
        if self.fail_second_once:
            self.fail_second_once = False
            raise RuntimeError("second failed")
        self.next_id += 1
        return self.next_id


async def store(tmp_path: Path) -> AlertStore:
    result = AlertStore(tmp_path / "delivery.db")
    await result.initialize()
    return result


@pytest.mark.asyncio
async def test_concurrent_bundles_never_interleave(tmp_path: Path):
    telegram = FakeTelegram()
    delivery = AlertDelivery(telegram, await store(tmp_path))
    a, b = token("CA-A", "A"), token("CA-B", "B")

    await asyncio.gather(
        delivery.send_alert_bundle(a, None, "A: second"),
        delivery.send_alert_bundle(b, None, "B: second"),
    )

    simplified = [(call[0], call[1]) for call in telegram.calls]
    assert simplified in [
        [("A", "card"), ("A", "second"), ("B", "card"), ("B", "second")],
        [("B", "card"), ("B", "second"), ("A", "card"), ("A", "second")],
    ]


@pytest.mark.asyncio
async def test_card_failure_leaves_pending_and_skips_second(tmp_path: Path):
    telegram = FakeTelegram()
    telegram.fail_card = True
    alert_store = await store(tmp_path)
    delivery = AlertDelivery(telegram, alert_store)

    with pytest.raises(RuntimeError, match="card failed"):
        await delivery.send_alert_bundle(token("CA-A", "A"), None, "A: second")

    state = await alert_store.get_delivery("CA-A")
    assert state and state.delivery_status == "pending"
    assert telegram.calls == [("A", "card")]


@pytest.mark.asyncio
async def test_second_retry_does_not_duplicate_card(tmp_path: Path):
    telegram = FakeTelegram()
    telegram.fail_second_once = True
    alert_store = await store(tmp_path)
    delivery = AlertDelivery(telegram, alert_store)
    item = token("CA-A", "A")

    with pytest.raises(RuntimeError, match="second failed"):
        await delivery.send_alert_bundle(item, None, "A: second")
    state = await alert_store.get_delivery("CA-A")
    assert state and state.delivery_status == "card_sent" and state.card_message_id == 101

    result = await delivery.send_alert_bundle(item, None, "A: second")
    assert result.status == "completed"
    assert [(call[0], call[1]) for call in telegram.calls] == [
        ("A", "card"),
        ("A", "second"),
        ("A", "second"),
    ]
