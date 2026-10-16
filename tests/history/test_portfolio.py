"""Tests for fin_tracker.history.portfolio (yfinance is faked)."""

import pandas as pd
import pytest

from fin_tracker.history.portfolio import (
    PORTFOLIO_HISTORY_COLUMNS,
    compute_portfolio_history,
    get_daily_price_eur,
)
from fin_tracker.ingestion import load_all_transactions
from tests.conftest import FAKE_TODAY, build_transactions

pytestmark = pytest.mark.usefixtures("fake_yfinance")


def test_get_daily_price_eur_covers_every_calendar_day():
    series_price = get_daily_price_eur(
        "IE00TEST0001", pd.Timestamp("2026-10-10"), FAKE_TODAY
    )
    assert len(series_price) == 6
    assert (series_price == 12.0).all()


def test_get_daily_price_eur_returns_none_without_price():
    assert (
        get_daily_price_eur("IE00NOPRICE0", pd.Timestamp("2026-10-10"), FAKE_TODAY)
        is None
    )


def test_compute_portfolio_history_tracks_shares_cost_and_value(path_raw_data):
    df_history = compute_portfolio_history(
        load_all_transactions(path_raw_data), FAKE_TODAY
    ).set_index("date")

    assert df_history.columns.tolist() == PORTFOLIO_HISTORY_COLUMNS[1:]
    assert df_history.index.min() == pd.Timestamp("2026-01-02")
    # Bought 10 for 101 EUR, sold 4 on 2026-02-01 (FIFO cost 6 * 10.1 left)
    assert df_history.loc["2026-01-15", "shares"] == 10.0
    assert df_history.loc["2026-02-01", "shares"] == 6.0
    assert df_history.loc["2026-02-01", "cost_basis_eur"] == pytest.approx(60.6)
    assert df_history.loc[FAKE_TODAY, "market_value_eur"] == pytest.approx(72.0)
    assert df_history.loc[FAKE_TODAY, "asset_bucket"] == "equity"


def test_compute_portfolio_history_drops_closed_and_keeps_unpriced_assets():
    df_transactions = build_transactions(
        [
            {"date": "2026-10-01", "account": "trade_republic", "transaction_type": "BUY",
             "asset_isin": "IE00TEST0001", "shares": 1.0, "amount": -10.0},
            {"date": "2026-10-05", "account": "trade_republic", "transaction_type": "SELL",
             "asset_isin": "IE00TEST0001", "shares": -1.0, "amount": 12.0},
            {"date": "2026-10-10", "account": "trade_republic", "transaction_type": "BUY",
             "asset_isin": "IE00NOPRICE0", "shares": 2.0, "amount": -20.0},
        ]
    )  # fmt: skip
    df_history = compute_portfolio_history(df_transactions, FAKE_TODAY)

    df_sold = df_history[df_history["asset_isin"] == "IE00TEST0001"]
    assert df_sold["date"].max() == pd.Timestamp("2026-10-04")
    df_unpriced = df_history[df_history["asset_isin"] == "IE00NOPRICE0"]
    assert df_unpriced["cost_basis_eur"].eq(20.0).all()
    assert df_unpriced["market_value_eur"].isna().all()


def test_compute_portfolio_history_without_trades_is_empty():
    df_history = compute_portfolio_history(
        build_transactions([{"date": "2026-10-01", "amount": -1.0}]), FAKE_TODAY
    )
    assert df_history.empty
    assert df_history.columns.tolist() == PORTFOLIO_HISTORY_COLUMNS
