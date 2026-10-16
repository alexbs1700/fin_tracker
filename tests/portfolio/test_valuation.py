"""Tests for fin_tracker.portfolio.valuation (yfinance is faked)."""

import pandas as pd
import pytest

from fin_tracker.ingestion import load_all_transactions
from fin_tracker.portfolio.valuation import (
    compute_cash_balances,
    compute_net_worth,
    value_positions,
)
from tests.conftest import TR_EXPECTED_CASH_EUR

pytestmark = pytest.mark.usefixtures("fake_yfinance")


@pytest.fixture
def df_transactions(path_raw_data):
    return load_all_transactions(path_raw_data)


def test_compute_cash_balances(df_transactions):
    df_cash_balances = compute_cash_balances(df_transactions).set_index(
        ["account", "sub_account"]
    )

    assert df_cash_balances.loc[("bbva", pd.NA), "balance_eur"] == 980.0
    assert (
        df_cash_balances.loc[("revolut", "Cuenta personal (EUR)"), "balance"] == 91.01
    )
    # 4000 HUF at 400 HUF per EUR
    assert df_cash_balances.loc[
        ("revolut", "Cuenta personal (HUF)"), "balance_eur"
    ] == pytest.approx(10.0)
    assert df_cash_balances.loc[
        ("trade_republic", "cash"), "balance_eur"
    ] == pytest.approx(TR_EXPECTED_CASH_EUR)


def test_compute_cash_balances_excludes_joint_account(df_transactions):
    row_joint = (
        compute_cash_balances(df_transactions)
        .set_index("sub_account")
        .loc["Cuenta Conjunta (EUR)"]
    )
    assert row_joint["balance_eur"] == 50.0
    assert row_joint["my_balance_eur"] == 0.0


def test_value_positions_prices_known_and_flags_unknown_assets():
    df_positions = pd.DataFrame(
        {
            "asset_isin": ["IE00TEST0001", "IE00NOPRICE0"],
            "shares": [6.0, 1.0],
            "cost_basis_eur": [60.0, 10.0],
        }
    )
    df_valued = value_positions(df_positions).set_index("asset_isin")

    assert df_valued.loc["IE00TEST0001", "market_value_eur"] == 72.0
    assert df_valued.loc["IE00TEST0001", "unrealized_gain_eur"] == 12.0
    assert df_valued.loc["IE00TEST0001", "unrealized_return"] == pytest.approx(0.2)
    assert pd.isna(df_valued.loc["IE00NOPRICE0", "market_value_eur"])
    assert pd.isna(df_valued.loc["IE00NOPRICE0", "ticker"])


def test_compute_net_worth(df_transactions):
    dict_results = compute_net_worth(df_transactions)
    df_net_worth = dict_results["df_net_worth"].set_index(["account", "asset_type"])

    assert set(dict_results) == {
        "df_cash_balances",
        "df_positions",
        "df_realized_gains",
        "df_net_worth",
    }
    # Revolut: 91.01 EUR + 10 EUR of HUF, joint account excluded
    assert df_net_worth.loc[("revolut", "cash"), "value_eur"] == pytest.approx(101.01)
    # 6 shares left at 12 EUR
    assert df_net_worth.loc[
        ("trade_republic", "investments"), "value_eur"
    ] == pytest.approx(72.0)
    assert len(dict_results["df_realized_gains"]) == 1
