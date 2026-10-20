"""Fixtures for demo mode tests."""

import pandas as pd
import pytest

from fin_tracker.portfolio import market_data
from fin_tracker.storage import price_cache

# Fixed end of the demo so every test sees the same months
DEMO_END_DATE = pd.Timestamp("2026-10-20")


@pytest.fixture
def restore_market(monkeypatch: pytest.MonkeyPatch):
    """Undo ``install_demo_market`` after the test (it patches process globals)."""
    monkeypatch.setattr(market_data.yf, "Ticker", market_data.yf.Ticker)
    monkeypatch.setattr(price_cache, "PATH_PRICE_CACHE", price_cache.PATH_PRICE_CACHE)
    yield
    market_data.get_eur_per_unit.cache_clear()
    market_data.get_latest_quote.cache_clear()
