"""Tests for fin_tracker.api.routes.spending."""

import pandas as pd
import pytest

from fin_tracker.api.routes.spending import (
    add_month,
    get_merchant,
    summarize_flows,
    summarize_monthly_cash_flow,
)
from fin_tracker.categorization.rules import FLOW_TYPES
from tests.conftest import build_transactions


@pytest.fixture
def df_transactions():
    df_transactions = build_transactions(
        [
            {"date": "2026-01-05", "account": "bbva", "amount": 2000.0, "description": "Abono de nómina"},
            {"date": "2026-01-06", "account": "bbva", "amount": -500.0, "description": "Transferencia realizada", "transaction_type": "Alquiler"},
            {"date": "2026-01-07", "account": "bbva", "amount": -50.0, "description": "Mercadona"},
            {"date": "2026-02-07", "account": "bbva", "amount": -30.0, "description": "Mercadona"},
            {"date": "2026-02-08", "account": "bbva", "amount": -300.0, "description": "Transferencia realizada", "transaction_type": "Monthly investment"},
            {"date": "2026-02-09", "account": "trade_republic", "amount": -100.0, "fee": -1.0, "fee_eur": -1.0, "transaction_type": "BUY"},
        ]
    )  # fmt: skip
    df_transactions["flow_type"] = pd.Categorical(
        ["income", "expense", "expense", "expense", "internal_transfer", "investment"],
        categories=FLOW_TYPES,
    )
    df_transactions["category"] = pd.Series(
        ["Nómina", "Vivienda", "Supermercado", "Supermercado", "Traspaso interno", "Inversión"],
        dtype="string",
    )  # fmt: skip
    return df_transactions


def test_add_month(df_transactions):
    assert add_month(df_transactions)["month"].iloc[0] == "2026-01"


def test_get_merchant_uses_transaction_type_for_generic_descriptions(df_transactions):
    assert get_merchant(df_transactions).tolist()[:3] == [
        "Abono de nómina",
        "Alquiler",
        "Mercadona",
    ]


def test_summarize_flows_expenses_by_category(df_transactions):
    df_expenses = df_transactions[df_transactions["flow_type"] == "expense"]
    df_summary = summarize_flows(df_expenses, "category")
    assert df_summary[
        ["category", "outflow_eur", "net_eur", "transactions"]
    ].values.tolist() == [
        ["Vivienda", 500.0, -500.0, 1],
        ["Supermercado", 80.0, -80.0, 2],
    ]


def test_summarize_flows_total_mixes_inflows_and_outflows(df_transactions):
    df_selected = df_transactions[
        df_transactions["flow_type"].isin(["income", "expense"])
    ]
    assert summarize_flows(df_selected, "total").iloc[0].to_dict() == {
        "inflow_eur": 2000.0,
        "outflow_eur": 580.0,
        "net_eur": 1420.0,
        "transactions": 4,
    }


def test_summarize_flows_sorts_months_and_limits(df_transactions):
    df_by_month = summarize_flows(df_transactions, "month_category")
    assert df_by_month["month"].tolist() == sorted(df_by_month["month"])
    assert len(summarize_flows(df_transactions, "merchant", limit=1)) == 1
    # Biggest absolute net first, whatever its sign
    assert (
        summarize_flows(df_transactions, "flow_type")["flow_type"].iloc[0] == "income"
    )


def test_summarize_monthly_cash_flow(df_transactions):
    df_monthly = summarize_monthly_cash_flow(df_transactions).set_index("month")

    assert df_monthly.loc["2026-01", "income_eur"] == 2000.0
    assert df_monthly.loc["2026-01", "expenses_eur"] == 550.0
    assert df_monthly.loc["2026-01", "savings_rate"] == pytest.approx(1450 / 2000)
    # Internal transfers count nowhere; the buy counts as invested, with its fee
    assert df_monthly.loc["2026-02", "expenses_eur"] == 30.0
    assert df_monthly.loc["2026-02", "invested_eur"] == 101.0
    assert pd.isna(df_monthly.loc["2026-02", "savings_rate"])


def test_monthly_cash_flow_endpoint(client):
    list_monthly = client.get(
        "/api/cash-flow/monthly", params={"date_from": "2026-01-01"}
    ).json()
    assert list_monthly[0]["month"] == "2026-01"
