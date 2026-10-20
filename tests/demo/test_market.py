"""Tests for fin_tracker.demo.market."""

import pandas as pd
import pytest

from fin_tracker.demo.market import (
    DEMO_ASSETS,
    PRICE_ORIGIN_DATE,
    DemoTicker,
    build_price_history,
    get_price_on,
    install_demo_market,
)
from fin_tracker.portfolio import market_data
from fin_tracker.storage import price_cache

ISIN_EQUITY = "IE00DEMO0001"


def test_build_price_history_starts_at_the_start_price_on_business_days():
    series_close = build_price_history(ISIN_EQUITY, pd.Timestamp("2023-03-31"))
    assert series_close.index[0] == PRICE_ORIGIN_DATE
    assert series_close.iloc[0] == DEMO_ASSETS[ISIN_EQUITY].start_price
    assert (series_close.index.dayofweek < 5).all()
    assert (series_close > 0).all()


def test_build_price_history_is_stable_when_the_end_date_moves():
    series_short = build_price_history(ISIN_EQUITY, pd.Timestamp("2025-01-31"))
    series_long = build_price_history(ISIN_EQUITY, pd.Timestamp("2026-01-31"))
    pd.testing.assert_series_equal(
        series_short, series_long.loc[: series_short.index[-1]]
    )


def test_build_price_history_differs_per_asset():
    end_date = pd.Timestamp("2024-01-31")
    series_equity = build_price_history(ISIN_EQUITY, end_date)
    series_bond = build_price_history("IE00DEMO0003", end_date)
    assert (series_equity / series_equity.iloc[0]).iloc[-1] != pytest.approx(
        (series_bond / series_bond.iloc[0]).iloc[-1]
    )


def test_build_price_history_rejects_unknown_isins():
    with pytest.raises(KeyError):
        build_price_history("US0000000000", pd.Timestamp("2024-01-31"))


def test_get_price_on_a_weekend_uses_the_previous_close():
    friday, sunday = pd.Timestamp("2025-06-06"), pd.Timestamp("2025-06-08")
    assert get_price_on(ISIN_EQUITY, sunday) == get_price_on(ISIN_EQUITY, friday)


def test_demo_ticker_serves_assets_in_eur_with_a_utc_index():
    ticker = DemoTicker(ISIN_EQUITY, end_date=pd.Timestamp("2025-06-06"))
    df_history = ticker.history(start="2025-06-02")
    assert ticker.fast_info == {"currency": "EUR"}
    assert len(df_history) == 5
    assert str(df_history.index.tz) == "UTC"
    assert df_history["Close"].iloc[-1] == get_price_on(
        ISIN_EQUITY, pd.Timestamp("2025-06-06")
    )


def test_demo_ticker_defaults_to_the_last_week():
    df_history = DemoTicker(ISIN_EQUITY, end_date=pd.Timestamp("2025-06-06")).history(
        period="5d"
    )
    assert df_history.index[0] >= pd.Timestamp("2025-05-30", tz="UTC")


def test_demo_ticker_serves_constant_fx_pairs():
    ticker = DemoTicker("EURHUF=X", end_date=pd.Timestamp("2025-06-06"))
    assert ticker.fast_info == {"currency": "HUF"}
    assert (ticker.history(period="5d")["Close"] == 400.0).all()


def test_demo_ticker_returns_nothing_for_unknown_symbols():
    ticker = DemoTicker("AAPL", end_date=pd.Timestamp("2025-06-06"))
    assert ticker.fast_info == {"currency": None}
    assert ticker.history(period="5d").empty


def test_install_demo_market_routes_yfinance_and_the_cache(restore_market, tmp_path):
    install_demo_market(tmp_path / "prices")
    assert market_data.yf.Ticker is DemoTicker
    assert tmp_path / "prices" == price_cache.PATH_PRICE_CACHE
    assert market_data.get_eur_per_unit("HUF") == pytest.approx(1 / 400)
    assert market_data.get_latest_quote(ISIN_EQUITY).listing_currency == "EUR"
