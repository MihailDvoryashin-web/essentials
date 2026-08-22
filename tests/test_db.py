from pathlib import Path

import pytest

from essentials.db import AlertStore


@pytest.mark.asyncio
async def test_ca_is_persistently_deduplicated(tmp_path: Path):
    path = tmp_path / "alerts.db"
    first_process = AlertStore(path)
    await first_process.initialize()
    assert not await first_process.contains("CA")
    await first_process.record("CA", 123)

    simulated_restart = AlertStore(path)
    await simulated_restart.initialize()
    assert await simulated_restart.contains("CA")


@pytest.mark.asyncio
async def test_delivery_state_transitions_and_fields(tmp_path: Path):
    store = AlertStore(tmp_path / "delivery.db")
    await store.initialize()

    await store.ensure_pending("CA2", "-100123", 3)
    pending = await store.get_delivery("CA2")
    assert pending is not None
    assert pending.delivery_status == "pending"
    assert pending.telegram_chat_id == "-100123"
    assert pending.telegram_thread_id == 3
    assert not await store.contains("CA2")

    await store.mark_card_sent("CA2", 101)
    card_sent = await store.get_delivery("CA2")
    assert card_sent is not None
    assert card_sent.delivery_status == "card_sent"
    assert card_sent.card_message_id == 101
    assert not await store.contains("CA2")

    await store.mark_completed("CA2", 102)
    completed = await store.get_delivery("CA2")
    assert completed is not None
    assert completed.delivery_status == "completed"
    assert completed.data_message_id == 102
    assert await store.contains("CA2")
