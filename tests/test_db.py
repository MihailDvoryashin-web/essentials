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
