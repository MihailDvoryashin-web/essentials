from __future__ import annotations

import asyncio
import logging

from .db import AlertStore
from .delivery import AlertDelivery
from .gmgn import GmgnClient
from .image_resolver import ImageResolver

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self, gmgn: GmgnClient, delivery: AlertDelivery, store: AlertStore, poll_seconds: int, image_resolver: ImageResolver):
        self.gmgn = gmgn
        self.delivery = delivery
        self.store = store
        self.poll_seconds = poll_seconds
        self.image_resolver = image_resolver

    async def run_once(self) -> int:
        candidates = await self.gmgn.fetch_candidates()
        sent = 0
        seen_in_batch: set[str] = set()
        for token in candidates:
            if token.address in seen_in_batch or await self.store.contains(token.address):
                continue
            seen_in_batch.add(token.address)
            try:
                image = await self.image_resolver.resolve(token)
                await self.delivery.send_alert_bundle(token, image)
            except Exception:
                logger.exception("Failed to alert token %s", token.address)
                continue
            sent += 1
            logger.info("Alerted %s (%s)", token.address, token.symbol)
        return sent

    async def run_forever(self) -> None:
        await self.store.initialize()
        while True:
            try:
                count = await self.run_once()
                logger.info("Polling cycle complete; sent=%d", count)
            except Exception:
                logger.exception("Polling cycle failed")
            await asyncio.sleep(self.poll_seconds)
