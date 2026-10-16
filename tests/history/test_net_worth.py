"""Tests for fin_tracker.history.net_worth (yfinance is faked)."""

import pandas as pd
import pytest

from fin_tracker.history.net_worth import (
    compute_net_worth_history,
    summarize_liquidity,
    summarize_monthly_stats,
)
from fin_tracker.ingestion import load_all_transactions
from tests.conftest import FAKE_TODAY, TR_EXPECTED_CASH_EUR

pytestmark = pytest.mark.usefixtures("fake_yfinance")


@pytest.fixture
def df_net_worth_history(path_raw_data):
    return compute_net_worth_history(load_all_transactions(path_raw_data), FAKE_TODAY)


def test_compute_net_worth_history_splits_cash_and_investments(df_net_worth_history):
    df_today = df_net_worth_history[df_net_worth_history["date"] == FAKE_TODAY]
    dict_values = df_today.set_index(["account", "asset_type"])["value_eur"].to_dict()

    assert dict_values[("bbva", "cash")] == 980.0
    # 91.01 EUR + 10 EUR of HUF; the joint account counts 0
    assert dict_values[("revolut", "cash")] == pytest.approx(101.01)
    assert dict_values[("trade_republic", "cash")] == pytest.approx(
        TR_EXPECTED_CASH_EUR
    )
    assert dict_values[("trade_republic", "investments")] == pytest.approx(72.0)


def test_summarize_liquidity_totals_per_day(df_net_worth_history):
    df_liquidity = summarize_liquidity(df_net_worth_history).set_index("date")

    assert df_liquidity.columns.tolist() == ["cash_eur", "investments_eur", "total_eur"]
    # Before the first trade there are no investments
    assert df_liquidity.loc[pd.Timestamp("2026-01-01"), "investments_eur"] == 0.0
    assert df_liquidity.loc[FAKE_TODAY, "total_eur"] == pytest.approx(
        980.0 + 101.01 + TR_EXPECTED_CASH_EUR + 72.0
    )


def test_summarize_monthly_stats_describes_each_month():
    df_liquidity = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03", "2026-02-01"]
            ),
            "total_eur": [100.0, 400.0, 200.0, 50.0],
        }
    )
    df_stats = summarize_monthly_stats(df_liquidity, "total_eur").set_index("month")

    assert df_stats.loc["2026-01", "min_eur"] == 100.0
    assert df_stats.loc["2026-01", "max_eur"] == 400.0
    assert df_stats.loc["2026-01", "mean_eur"] == pytest.approx(700 / 3)
    assert df_stats.loc["2026-01", "median_eur"] == 200.0
    assert df_stats.loc["2026-01", "min_date"] == pd.Timestamp("2026-01-01")
    assert df_stats.loc["2026-01", "max_date"] == pd.Timestamp("2026-01-02")
    assert df_stats.loc["2026-01", "days"] == 3
    # Only 3 of 31 days observed: the month is incomplete
    assert df_stats.loc["2026-01", "is_partial"]


def test_summarize_monthly_stats_full_month_is_not_partial(df_net_worth_history):
    df_stats = summarize_monthly_stats(
        summarize_liquidity(df_net_worth_history), "cash_eur"
    ).set_index("month")
    assert not df_stats.loc["2026-09", "is_partial"]
    assert df_stats.loc["2026-10", "is_partial"]
