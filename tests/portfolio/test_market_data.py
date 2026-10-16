"""Tests for fin_tracker.portfolio.market_data (yfinance is faked)."""

import pandas as pd
import pytest

from fin_tracker.portfolio.market_data import (
    get_eur_per_unit,
    get_latest_quote,
    resolve_ticker,
)


def test_resolve_ticker_uses_override_then_falls_back_to_isin():
    assert resolve_ticker("IE00B4L5Y983") == "EUNL.DE"
    assert resolve_ticker("IE00UNKNOWN0") == "IE00UNKNOWN0"


@pytest.mark.usefixtures("fake_yfinance")
class TestGetEurPerUnit:
    def test_eur_is_one(self):
        assert get_eur_per_unit("EUR") == 1.0

    def test_inverts_units_per_eur(self):
        # EURUSD = 1.25 USD per EUR -> 1 USD = 0.8 EUR
        assert get_eur_per_unit("USD") == pytest.approx(0.8)

    def test_pence_are_a_hundredth_of_a_pound(self):
        assert get_eur_per_unit("GBp") == pytest.approx(1 / 0.8 / 100)

    def test_raises_without_fx_data(self):
        with pytest.raises(ValueError, match="XXX"):
            get_eur_per_unit("XXX")


@pytest.mark.usefixtures("fake_yfinance")
class TestGetLatestQuote:
    def test_eur_listing_keeps_price(self):
        quote = get_latest_quote("IE00TEST0001")
        assert quote.price == quote.price_eur == 12.0
        assert quote.price_date == pd.Timestamp("2026-10-15")

    def test_foreign_listing_is_converted_to_eur(self):
        quote = get_latest_quote("USD.TEST")
        assert quote.listing_currency == "USD"
        assert quote.price_eur == pytest.approx(10.0 * 0.8)

    def test_unknown_ticker_returns_none(self):
        assert get_latest_quote("NOPE") is None
