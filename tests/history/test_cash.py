"""Tests for fin_tracker.history.cash (yfinance is faked)."""

import pandas as pd
import pytest

from fin_tracker.history.cash import (
    compute_cash_history,
    compute_running_balance_history,
    compute_trade_republic_cash_history,
)
from fin_tracker.ingestion import load_all_transactions
from tests.conftest import FAKE_TODAY, TR_EXPECTED_CASH_EUR

pytestmark = pytest.mark.usefixtures("fake_yfinance")


@pytest.fixture
def df_transactions(path_raw_data):
    return load_all_transactions(path_raw_data)


def get_balance(df_history: pd.DataFrame, date: str, sub_account) -> float:
    """Balance of one wallet on one day (``sub_account`` None for BBVA)."""
    is_wallet = (
        df_history["sub_account"].isna()
        if sub_account is None
        else df_history["sub_account"] == sub_account
    )
    return df_history.loc[
        is_wallet & (df_history["date"] == pd.Timestamp(date)), "balance"
    ].item()


def test_running_balance_history_carries_last_balance_forward(df_transactions):
    df_history = compute_running_balance_history(df_transactions, FAKE_TODAY)

    assert get_balance(df_history, "2026-01-01", None) == 1000.0
    assert get_balance(df_history, "2026-01-15", None) == 1000.0
    assert get_balance(df_history, "2026-02-02", None) == 980.0
    assert get_balance(df_history, "2026-10-15", "Cuenta personal (EUR)") == 91.01
    assert df_history["date"].max() == FAKE_TODAY


def test_trade_republic_cash_history_is_cumulative_net_cash(df_transactions):
    df_history = compute_trade_republic_cash_history(df_transactions, FAKE_TODAY)

    assert df_history["balance"].iloc[0] == 1000.0
    # After the buy of 100 + 1 fee
    assert get_balance(df_history, "2026-01-02", "cash") == 899.0
    assert df_history["balance"].iloc[-1] == pytest.approx(TR_EXPECTED_CASH_EUR)


def test_compute_cash_history_converts_fx_and_applies_ownership(df_transactions):
    df_history = compute_cash_history(df_transactions, FAKE_TODAY)
    df_today = df_history[df_history["date"] == FAKE_TODAY].set_index("sub_account")

    # 4000 HUF at 400 HUF per EUR
    assert df_today.loc["Cuenta personal (HUF)", "balance_eur"] == pytest.approx(10.0)
    assert df_today.loc["Cuenta Conjunta (EUR)", "balance_eur"] == 50.0
    assert df_today.loc["Cuenta Conjunta (EUR)", "my_balance_eur"] == 0.0
    assert df_today.loc["cash", "my_balance_eur"] == pytest.approx(TR_EXPECTED_CASH_EUR)
