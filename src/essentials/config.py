from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_alerts_thread_id: int | None
    database_path: Path
    poll_interval_seconds: int = 60
    gmgn_cli_bin: str = "gmgn-cli"
    gmgn_cli_timeout_seconds: int = 45
    http_timeout_seconds: int = 15
    max_retries: int = 3
    log_level: str = "INFO"
    axiom_emoji_id: str | None = None
    gmgn_emoji_id: str | None = None
    padre_emoji_id: str | None = None
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"

    @classmethod
    def from_env(cls) -> "Settings":
        # gmgn-cli reads GMGN_API_KEY itself; validating it here makes startup fail fast.
        _required("GMGN_API_KEY")
        return cls(
            telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_required("TELEGRAM_CHAT_ID"),
            telegram_alerts_thread_id=_optional_positive_int("TELEGRAM_ALERTS_THREAD_ID"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/essentials.db")),
            poll_interval_seconds=_positive_int("POLL_INTERVAL_SECONDS", 60),
            gmgn_cli_bin=os.getenv("GMGN_CLI_BIN", "gmgn-cli").strip() or "gmgn-cli",
            gmgn_cli_timeout_seconds=_positive_int("GMGN_CLI_TIMEOUT_SECONDS", 45),
            http_timeout_seconds=_positive_int("HTTP_TIMEOUT_SECONDS", 15),
            max_retries=_positive_int("MAX_RETRIES", 3),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            axiom_emoji_id=os.getenv("AXIOM_EMOJI_ID") or None,
            gmgn_emoji_id=os.getenv("GMGN_EMOJI_ID") or None,
            padre_emoji_id=os.getenv("PADRE_EMOJI_ID") or None,
            solana_rpc_url=os.getenv("SOLANA_RPC_URL", "").strip() or "https://api.mainnet-beta.solana.com",
        )
