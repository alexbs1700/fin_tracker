"""Tests for fin_tracker.projections.baseline."""

import pandas as pd
import pytest

from fin_tracker.categorization.rules import FLOW_TYPES
from fin_tracker.config import (
    ASSET_BUCKET_EXPECTED_RETURN,
    ASSET_BUCKET_VOLATILITY,
    TRADE_REPUBLIC_CASH_INTEREST_RATE,
)
from fin_tracker.projections.baseline import (
    compute_cash_return,
    compute_invested_salary_share,
    compute_monthly_averages,
    compute_portfolio_assumptions,
    estimate_baseline,
    estimate_current_salary,
    get_complete_months,
)
from tests.conftest import build_transactions

TODAY = pd.Timestamp("2026-10-15")


@pytest.fixture
def df_transactions():
    df_transactions = build_transactions(
        [
            {"date": "2025-09-30", "amount": 9999.0},  # outside the 12 months
            {"date": "2025-10-01", "amount": 2400.0},
            {"date": "2026-06-30", "amount": 1200.0},
            {"date": "2026-07-01", "amount": 120.0},
            {"date": "2026-08-01", "amount": -1200.0},
            {"date": "2026-09-01", "amount": -100.0, "fee": -1.0, "fee_eur": -1.0},
            {"date": "2026-10-01", "amount": -5000.0},  # current month, incomplete
            {"date": "2026-06-12", "amount": 900.0},  # IRPF refund, modelled apart
        ]
    )
    df_transactions["flow_type"] = pd.Categorical(
        [
            "income",
            "income",
            "income",
            "income",
            "expense",
            "investment",
            "expense",
            "income",
        ],
        categories=FLOW_TYPES,
    )
    df_transactions["category"] = pd.Series(
        ["Nómina", "Nómina", "Nómina", "Bizum recibido", "Vivienda", "Inversión", "Viajes", "Devolución IRPF"],
        dtype="string",
    )  # fmt: skip
    return df_transactions


def test_get_complete_months_drops_current_and_old_months(df_transactions):
    df_recent = get_complete_months(df_transactions, TODAY)
    assert sorted(df_recent["date"].dt.strftime("%Y-%m").tolist()) == [
        "2025-10",
        "2026-06",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]


def test_compute_monthly_averages_spreads_over_the_year(df_transactions):
    dict_averages = compute_monthly_averages(
        get_complete_months(df_transactions, TODAY)
    )
    # Salary and the IRPF refund come from the payroll model, not from here
    assert dict_averages == pytest.approx(
        {
            "monthly_other_income_eur": 120 / 12,
            "monthly_expenses_eur": 1200 / 12,
            "monthly_investment_eur": 101 / 12,
        }
    )


def test_compute_cash_return_weights_trade_republic_cash():
    df_cash_balances = pd.DataFrame(
        {"account": ["bbva", "trade_republic"], "my_balance_eur": [750.0, 250.0]}
    )
    assert compute_cash_return(df_cash_balances) == pytest.approx(
        0.25 * TRADE_REPUBLIC_CASH_INTEREST_RATE
    )
    assert compute_cash_return(df_cash_balances.iloc[0:0]) == 0.0


def test_compute_portfolio_assumptions_weights_buckets():
    df_positions = pd.DataFrame(
        {"asset_bucket": ["equity", "fixed_income"], "market_value_eur": [75.0, 25.0]}
    )
    dict_assumptions = compute_portfolio_assumptions(df_positions)
    assert dict_assumptions["investment_return"] == pytest.approx(
        0.75 * ASSET_BUCKET_EXPECTED_RETURN["equity"]
        + 0.25 * ASSET_BUCKET_EXPECTED_RETURN["fixed_income"]
    )
    assert dict_assumptions["investment_volatility"] == pytest.approx(
        0.75 * ASSET_BUCKET_VOLATILITY["equity"]
        + 0.25 * ASSET_BUCKET_VOLATILITY["fixed_income"]
    )


def test_compute_portfolio_assumptions_without_positions_uses_equity():
    df_positions = pd.DataFrame({"asset_bucket": [], "market_value_eur": []})
    assert (
        compute_portfolio_assumptions(df_positions)["investment_return"]
        == (ASSET_BUCKET_EXPECTED_RETURN["equity"])
    )


def test_estimate_baseline_combines_everything(df_transactions):
    dict_net_worth = {
        "df_cash_balances": pd.DataFrame(
            {"account": ["bbva"], "my_balance_eur": [1000.0]}
        ),
        "df_positions": pd.DataFrame(
            {"asset_bucket": ["equity"], "market_value_eur": [500.0]}
        ),
    }
    dict_baseline = estimate_baseline(df_transactions, dict_net_worth, TODAY)
    assert dict_baseline["start_cash_eur"] == 1000.0
    assert dict_baseline["start_investments_eur"] == 500.0
    assert dict_baseline["cash_return"] == 0.0
    assert dict_baseline["payments_per_year"] == 14
    assert dict_baseline["investment_mode"] == "fixed"
    assert dict_baseline["investment_plan"] == [
        {"year": 2026, "salary_percent": round(101 / 3600, 3)}
    ]
    assert dict_baseline["salary_schedule"][0]["start_month"] == "2026-06"


def test_estimate_current_salary_uses_the_latest_regular_payslip(df_transactions):
    # July and December carry extra pays or bonus, June is the latest regular month
    dict_step = estimate_current_salary(df_transactions, TODAY)
    assert dict_step["start_month"] == "2026-06"
    assert dict_step["gross_bonus_eur"] == 0
    assert dict_step["gross_salary_eur"] > 1200 * 14


def test_estimate_current_salary_without_salary():
    df_empty = build_transactions([{"date": "2026-01-01", "amount": 1.0}])
    df_empty["category"] = pd.Series(["Otros"], dtype="string")
    assert estimate_current_salary(df_empty, TODAY) is None


def test_compute_invested_salary_share(df_transactions):
    df_recent = get_complete_months(df_transactions, TODAY)
    # 101 EUR invested (fee included) out of 3.600 EUR of salary
    assert compute_invested_salary_share(df_recent) == pytest.approx(101 / 3600)
    df_no_salary = df_recent[df_recent["category"] != "Nómina"]
    assert compute_invested_salary_share(df_no_salary) == 0.0
