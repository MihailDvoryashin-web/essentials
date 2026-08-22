from __future__ import annotations

import asyncio
import json
from typing import Any

from .models import Token
from .retry import with_retry


class GmgnError(RuntimeError):
    pass


class GmgnClient:
    def __init__(self, executable: str, timeout_seconds: int, max_retries: int):
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def command(self) -> list[str]:
        return [
            self.executable, "market", "trenches",
            "--chain", "sol",
            "--type", "new_creation", "near_completion", "completed",
            "--launchpad-platform", "Pump.fun",
            "--min-marketcap", "50000",
            "--max-marketcap", "250000",
            "--min-total-fee", "5",
            "--min-renowned-count", "1",
            "--limit", "80",
            "--raw",
        ]

    async def fetch_candidates(self) -> list[Token]:
        return await with_retry(self._fetch_once, attempts=self.max_retries)

    async def _fetch_once(self) -> list[Token]:
        try:
            process = await asyncio.create_subprocess_exec(
                *self.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise GmgnError(f"GMGN CLI not found: {self.executable}") from exc
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise GmgnError("GMGN CLI timed out") from exc
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()[-1000:]
            raise GmgnError(f"GMGN CLI exited with {process.returncode}: {detail}")
        payload = self._parse_json(stdout.decode(errors="replace"))
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise GmgnError("GMGN response has no data object")
        items: list[dict[str, Any]] = []
        for key in ("new_creation", "pump", "completed"):
            group = data.get(key, [])
            if isinstance(group, list):
                items.extend(item for item in group if isinstance(item, dict))
        tokens = (Token.from_gmgn(item) for item in items)
        return [token for token in tokens if token is not None and token.passes_stage1()]

    @staticmethod
    def _parse_json(output: str) -> dict[str, Any]:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise GmgnError("GMGN CLI returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise GmgnError("GMGN CLI returned a non-object response")
        return payload

