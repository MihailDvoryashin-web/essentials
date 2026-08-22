from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class Token:
    address: str
    symbol: str
    name: str
    market_cap: Decimal
    total_fee: Decimal
    renowned_count: int
    logo_url: str | None
    twitter: str | None
    has_social: bool
    launchpad_platform: str
    axiom_market_address: str | None
    logo_small_base64: str | None = None

    @staticmethod
    def market_cap_from_gmgn(item: dict[str, Any]) -> Decimal | None:
        """Parse the GMGN Trenches `market_cap` field, already expressed in USD."""
        return _decimal(item.get("market_cap"))

    @staticmethod
    def has_social_from_gmgn(item: dict[str, Any]) -> bool:
        """A Trenches token has social data when any real social field is non-empty."""
        return any(_text(item.get(field)) is not None for field in ("twitter", "website", "telegram"))

    @classmethod
    def from_gmgn(cls, item: dict[str, Any]) -> "Token | None":
        address = _text(item.get("address"))
        market_cap = cls.market_cap_from_gmgn(item)
        total_fee = _decimal(item.get("total_fee"))
        if not address or market_cap is None or total_fee is None:
            return None
        try:
            renowned_count = int(item.get("renowned_count", 0))
        except (TypeError, ValueError):
            return None

        has_social = cls.has_social_from_gmgn(item)

        # Axiom requires a GMGN-supplied market/pool identifier, not an invented CA route.
        axiom_address = _text(item.get("market_address")) or _text(item.get("pair_address")) or _text(item.get("pool_address"))
        return cls(
            address=address,
            symbol=_text(item.get("symbol")) or "?",
            name=_text(item.get("name")) or "Unknown",
            market_cap=market_cap,
            total_fee=total_fee,
            renowned_count=renowned_count,
            logo_url=_text(item.get("logo")),
            twitter=_text(item.get("twitter")),
            has_social=has_social,
            launchpad_platform=_text(item.get("launchpad_platform")) or "",
            axiom_market_address=axiom_address,
            logo_small_base64=_text(item.get("logo_small_base64")),
        )

    def passes_stage1(self) -> bool:
        return (
            self.launchpad_platform == "Pump.fun"
            and Decimal("50000") <= self.market_cap <= Decimal("250000")
            and self.has_social
            and self.total_fee >= Decimal("5")
            and self.renowned_count >= 1
        )
