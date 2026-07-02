"""Tests for CUSIP-to-ticker resolution (cusip_map.py)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.research.data.cusip_map import CusipResolver, CusipResolution


def test_resolve_known_apple():
    """037833100 → AAPL (Apple Inc., builtin)."""
    r = CusipResolver()
    result = r.resolve("037833100")
    assert result.ticker == "AAPL"
    assert result.company_name == "Apple Inc."
    assert result.exchange == "NASDAQ"
    assert result.source == "builtin"


def test_resolve_known_microsoft():
    r = CusipResolver()
    result = r.resolve("594918104")
    assert result.ticker == "MSFT"
    assert result.source == "builtin"


def test_resolve_known_berkshire():
    r = CusipResolver()
    result = r.resolve("084670702")
    assert result.ticker == "BRK.B"
    assert result.source == "builtin"


def test_resolve_known_brk_a():
    """Separate CUSIP for BRK.A."""
    r = CusipResolver()
    result = r.resolve("084670108")
    assert result.ticker == "BRK.A"


def test_resolve_brk_b_via_num():
    """084670702 is BRK.B via builtin."""
    r = CusipResolver()
    result = r.resolve("084670702")
    assert result.ticker == "BRK.B"


def test_resolve_unknown_cusip_returns_none():
    r = CusipResolver()
    result = r.resolve("ZZZZZZZZZ")  # invalid / unknown
    assert result.ticker is None
    assert result.source == "not_found"


def test_resolve_many_deduplicates():
    r = CusipResolver()
    results = r.resolve_many(["037833100", "037833100", "ZZZZZZZZZ"])
    assert len(results) == 2  # unique CUSIPs
    assert results["037833100"].ticker == "AAPL"
    assert results["ZZZZZZZZZ"].ticker is None


def test_builtin_count():
    r = CusipResolver()
    assert r.builtin_count >= 150  # we have at minimum 150+ CUSIPs


def test_resolution_object_structure():
    r = CusipResolver()
    result = r.resolve("037833100")
    assert isinstance(result, CusipResolution)
    assert result.ticker is not None
    assert result.company_name is not None
    assert result.exchange is not None
    assert result.source in ("builtin", "cache", "edgar_fallback", "not_found")


def test_cusip_normalisation():
    """CUSIPs should be matchable with or without whitespace."""
    r = CusipResolver()
    assert r.resolve(" 037833100 ").source == "builtin"
    assert r.resolve("037833100").source == "builtin"


def test_stats():
    r = CusipResolver()
    stats = r.stats()
    assert stats["builtin_entries"] >= 150
    assert "cache_path" in stats
    assert "has_edgar_fallback" in stats


def test_top_holdings_known():
    """Check that a representative set of major holdings resolves."""
    expected = {
        "037833100": "AAPL",
        "594918104": "MSFT",
        "023135106": "AMZN",
        "67066G104": "NVDA",
        "30303M102": "META",
        "46625H100": "JPM",
        "92826C839": "V",
        "931142103": "WMT",
        "30231G102": "XOM",
        "166764100": "CVX",
    }
    r = CusipResolver()
    for cusip, expected_ticker in expected.items():
        result = r.resolve(cusip)
        assert result.ticker == expected_ticker, (
            f"CUSIP {cusip}: expected {expected_ticker}, got {result.ticker}"
        )
        assert result.source == "builtin"
