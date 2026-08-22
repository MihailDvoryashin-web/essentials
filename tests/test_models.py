from decimal import Decimal

from essentials.models import Token


def item(**overrides):
    value = {
        "address": "TokenCA",
        "symbol": "DOGE2",
        "name": "Doge2 Caesar",
        "market_cap": "87400",
        "total_fee": "5.1",
        "renowned_count": 1,
        "logo": "https://example.com/logo.png",
        "twitter": "https://x.com/user/status/123",
        "has_at_least_one_social": True,
        "launchpad_platform": "Pump.fun",
        "market_address": "AxiomMarket",
        "pool_address": "AxiomPool",
    }
    value.update(overrides)
    return value


def test_stage1_candidate_passes_all_conditions():
    token = Token.from_gmgn(item())
    assert token is not None
    assert token.passes_stage1()
    assert token.logo_url == "https://example.com/logo.png"
    assert token.twitter == "https://x.com/user/status/123"
    assert token.axiom_market_address == "AxiomMarket"


def test_every_stage1_boundary_is_enforced():
    failures = [
        {"market_cap": "49999.99"},
        {"market_cap": "250000.01"},
        {"total_fee": "4.999"},
        {"renowned_count": 0},
        {"twitter": "", "website": None, "telegram": None},
        {"launchpad_platform": "letsbonk"},
    ]
    for override in failures:
        token = Token.from_gmgn(item(**override))
        assert token is not None
        assert not token.passes_stage1(), override


def test_market_cap_boundaries_are_inclusive():
    low = Token.from_gmgn(item(market_cap=50000))
    high = Token.from_gmgn(item(market_cap=250000))
    assert low and high
    assert low.market_cap == Decimal("50000") and low.passes_stage1()
    assert high.market_cap == Decimal("250000") and high.passes_stage1()


def test_raw_trenches_market_cap_is_usd_without_scaling():
    accepted = Token.from_gmgn(item(market_cap=125000))
    below = Token.from_gmgn(item(market_cap=49999))
    above = Token.from_gmgn(item(market_cap=250001))

    assert accepted is not None and accepted.market_cap == Decimal("125000")
    assert accepted.passes_stage1()
    assert below is not None and not below.passes_stage1()
    assert above is not None and not above.passes_stage1()


def test_real_trenches_social_fields():
    passing = [
        {"twitter": "https://x.com/test", "website": None, "telegram": None},
        {"twitter": None, "website": "https://example.com", "telegram": None},
        {"twitter": None, "website": None, "telegram": "https://t.me/test"},
        {"twitter": "https://x.com/test", "website": "https://example.com", "telegram": None},
    ]
    for socials in passing:
        token = Token.from_gmgn(item(**socials, has_at_least_one_social=False))
        assert token is not None and token.has_social and token.passes_stage1(), socials

    rejected = Token.from_gmgn(item(
        twitter="",
        website="   ",
        telegram=None,
        has_at_least_one_social=True,
    ))
    assert rejected is not None
    assert not rejected.has_social
    assert not rejected.passes_stage1()


def test_ca_is_never_used_as_axiom_market_fallback():
    token = Token.from_gmgn(item(market_address=None, pair_address=None, pool_address=None))
    assert token is not None
    assert token.axiom_market_address is None
