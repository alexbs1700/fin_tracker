"""Tests for fin_tracker.projections.simulation."""

import numpy as np
import pandas as pd
import pytest

from fin_tracker.projections.payroll import SalaryStep
from fin_tracker.projections.simulation import (
    InvestmentPlanStep,
    ScenarioParameters,
    build_month_labels,
    build_monthly_flows,
    get_invested_share,
    simulate_paths,
    simulate_percentiles,
    simulate_scenario,
    summarize_projection,
    to_monthly_rate,
)

START_MONTH = pd.Period("2026-11", freq="M")


def test_to_monthly_rate_compounds_back_to_the_annual_rate():
    assert (1 + to_monthly_rate(0.06)) ** 12 == pytest.approx(1.06)
    assert to_monthly_rate(0.0) == 0.0


def test_months_and_labels():
    parameters = ScenarioParameters(horizon_years=2)
    assert parameters.months == 24
    list_labels = build_month_labels(parameters, START_MONTH)
    assert list_labels[0] == "2026-11"
    assert list_labels[-1] == "2028-10"


def test_build_monthly_flows_change_once_a_year():
    df_flows, df_payroll_years = build_monthly_flows(
        ScenarioParameters(
            horizon_years=2,
            salary_schedule=(SalaryStep("2026-01", 24000),),
            payments_per_year=12,
            monthly_expenses_eur=500,
            inflation=0.02,
            monthly_investment_eur=100,
            investment_growth=0.5,
        ),
        START_MONTH,
    )
    assert df_flows["salary_eur"].iloc[0] > 0
    assert df_flows["expenses_eur"].iloc[11] == 500
    assert df_flows["expenses_eur"].iloc[12] == pytest.approx(510)
    assert df_flows["contribution_eur"].iloc[12] == pytest.approx(150)
    # Refund of 2026 lands in June 2027 (8th projected month)
    assert df_flows["tax_refund_eur"].iloc[7] == pytest.approx(
        df_payroll_years.set_index("year").loc[2026, "refund_eur"]
    )


def test_simulate_paths_moves_contributions_from_cash_to_investments():
    parameters = ScenarioParameters(
        horizon_years=1,
        start_cash_eur=1000,
        monthly_other_income_eur=500,
        monthly_expenses_eur=300,
        monthly_investment_eur=100,
    )
    df_flows, _ = build_monthly_flows(parameters, START_MONTH)
    array_cash, array_investments = simulate_paths(
        parameters, df_flows, np.zeros((1, 12))
    )
    # Net 500 - 300 - 100 = +100 per month in cash, +100 per month invested
    assert array_cash[0, -1] == pytest.approx(1000 + 12 * 100)
    assert array_investments[0, -1] == pytest.approx(12 * 100)


def test_simulate_scenario_compounds_returns_and_deflates():
    parameters = ScenarioParameters(
        horizon_years=1,
        start_cash_eur=1000,
        start_investments_eur=1000,
        cash_return=0.02,
        investment_return=0.10,
        inflation=0.05,
    )
    df_projection, _ = simulate_scenario(parameters, START_MONTH)
    final_row = df_projection.iloc[-1]

    assert final_row["cash_eur"] == pytest.approx(1020)
    assert final_row["investments_eur"] == pytest.approx(1100)
    assert final_row["total_real_eur"] == pytest.approx(2120 / 1.05)
    assert final_row["invested_principal_eur"] == 1000
    assert df_projection["month"].iloc[0] == "2026-11"


def test_simulate_percentiles_spread_around_the_deterministic_path():
    parameters = ScenarioParameters(
        horizon_years=10,
        start_investments_eur=10000,
        investment_return=0.06,
        investment_volatility=0.15,
    )
    df_percentiles = simulate_percentiles(parameters, START_MONTH, simulations=2000)
    df_projection, _ = simulate_scenario(parameters, START_MONTH)
    deterministic_total = df_projection["total_eur"].iloc[-1]
    final_row = df_percentiles.iloc[-1]

    assert final_row["p10_eur"] < final_row["p50_eur"] < final_row["p90_eur"]
    # The median of a lognormal sits below its mean (the deterministic path)
    assert final_row["p50_eur"] < deterministic_total < final_row["p90_eur"]
    # Same seed, same result
    assert df_percentiles.equals(simulate_percentiles(parameters, START_MONTH, 2000))


def test_simulate_percentiles_without_volatility_matches_deterministic():
    parameters = ScenarioParameters(
        horizon_years=1, start_investments_eur=1000, investment_return=0.05
    )
    df_percentiles = simulate_percentiles(parameters, START_MONTH, simulations=10)
    assert df_percentiles["p10_eur"].iloc[-1] == pytest.approx(1050)
    assert df_percentiles["p90_eur"].iloc[-1] == pytest.approx(1050)


def test_summarize_projection_reports_gains_and_negative_cash():
    parameters = ScenarioParameters(
        horizon_years=1,
        start_cash_eur=100,
        start_investments_eur=1000,
        monthly_expenses_eur=50,
        monthly_investment_eur=10,
        investment_return=0.0,
    )
    dict_summary = summarize_projection(
        parameters, simulate_scenario(parameters, START_MONTH)[0]
    )
    assert dict_summary["total_contributions_eur"] == pytest.approx(120)
    assert dict_summary["investment_gains_eur"] == pytest.approx(0)
    assert dict_summary["start_total_eur"] == 1100
    # 100 - 60 per month: negative in the second month
    assert dict_summary["first_negative_cash_month"] == "2026-12"


PLAN = (InvestmentPlanStep(2028, 0.25), InvestmentPlanStep(2026, 0.10))


@pytest.mark.parametrize(
    ("year", "expected_share"),
    [(2025, 0.10), (2026, 0.10), (2027, 0.10), (2028, 0.25), (2040, 0.25)],
)
def test_get_invested_share_follows_the_plan(year, expected_share):
    assert get_invested_share(year, PLAN) == expected_share


def test_get_invested_share_without_plan():
    assert get_invested_share(2026, ()) == 0.0


def test_build_monthly_flows_invests_a_share_of_each_payslip():
    parameters = ScenarioParameters(
        horizon_years=2,
        salary_schedule=(SalaryStep("2026-01", 28000),),
        payments_per_year=14,
        investment_mode="salary_percent",
        investment_plan=(
            InvestmentPlanStep(2026, 0.10),
            InvestmentPlanStep(2027, 0.20),
        ),
        # Ignored in salary_percent mode
        monthly_investment_eur=999,
    )
    df_flows, _ = build_monthly_flows(parameters, START_MONTH)
    # Nov 2026 at 10 %, Dec 2026 includes the extra pay, 2027 at 20 %
    assert df_flows["contribution_eur"].iloc[0] == pytest.approx(
        0.10 * df_flows["salary_eur"].iloc[0]
    )
    assert df_flows["contribution_eur"].iloc[1] == pytest.approx(
        0.10 * df_flows["salary_eur"].iloc[1]
    )
    assert df_flows["contribution_eur"].iloc[1] > df_flows["contribution_eur"].iloc[0]
    assert df_flows["contribution_eur"].iloc[2] == pytest.approx(
        0.20 * df_flows["salary_eur"].iloc[2]
    )
