from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    retryable: Callable[[Exception], bool] | None = None,
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            if attempt == attempts or (retryable is not None and not retryable(exc)):
                raise
            delay = min(2 ** (attempt - 1), 15) + random.uniform(0, 0.25)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")

