"""Tests for fin_tracker.projections.payroll."""

import pandas as pd
import pytest

from fin_tracker.projections.payroll import (
    SalaryStep,
    build_payroll,
    build_salary_income,
    describe_payslips,
    get_salary_at,
    summarize_payroll_years,
)
from fin_tracker.taxes.spain import compute_tax_liability

SCHEDULE = (
    SalaryStep("2027-04", 40000, 4000),
    SalaryStep("2026-09", 35400, 3000),
)


@pytest.mark.parametrize(
    ("month", "expected"),
    [
        ("2026-01", (35400, 3000)),  # before the first step: first step
        ("2026-10", (35400, 3000)),
        ("2027-04", (40000, 4000)),
        ("2028-03", (40000, 4000)),
        ("2028-04", (40000 * 1.05, 4000 * 1.05)),  # growth after the last change
    ],
)
def test_get_salary_at(month, expected):
    assert get_salary_at(pd.Period(month, freq="M"), SCHEDULE, 0.05) == pytest.approx(
        expected
    )


def test_get_salary_at_without_steps():
    assert get_salary_at(pd.Period("2026-01", freq="M"), (), 0.05) == (0.0, 0.0)


def test_build_payroll_covers_whole_years_with_extras_and_bonus():
    df_payroll = build_payroll(SCHEDULE, 0.0, 14, 7, None, 2026, 2026).set_index(
        "month"
    )
    assert len(df_payroll) == 12
    # July: regular pay + extra pay + bonus
    assert df_payroll.loc["2026-07", "gross_eur"] == pytest.approx(
        2 * 35400 / 14 + 3000
    )
    assert df_payroll.loc["2026-12", "gross_eur"] == pytest.approx(2 * 35400 / 14)
    assert df_payroll["gross_eur"].sum() == pytest.approx(35400 + 3000)


def test_build_payroll_uses_the_override_rate():
    df_payroll = build_payroll(SCHEDULE, 0.0, 12, 7, 0.10, 2026, 2026)
    assert (df_payroll["retention_rate"] == 0.10).all()
    assert df_payroll["retention_eur"].iloc[0] == pytest.approx(0.10 * 35400 / 12)


def test_describe_payslips():
    dict_payslips = describe_payslips(35400, 3000, 14, 0.18)
    assert dict_payslips["extra_pay_net_eur"] == pytest.approx(35400 / 14 * 0.82)
    assert describe_payslips(35400, 0, 12, 0.18)["extra_pay_net_eur"] == 0
    # The bonus pays Social Security, unlike an extra pay
    assert dict_payslips["bonus_net_eur"] < 3000 * 0.82


def test_summarize_payroll_years_settles_the_real_tax():
    df_payroll = build_payroll(SCHEDULE, 0.0, 14, 7, None, 2026, 2027)
    df_years = summarize_payroll_years(df_payroll, 14).set_index("year")
    year_2026 = df_years.loc[2026]

    assert year_2026["gross_eur"] == pytest.approx(38400)
    assert year_2026["tax_liability_eur"] == pytest.approx(
        compute_tax_liability(year_2026["gross_eur"], year_2026["social_security_eur"])
    )
    # Madrid resident: withholding exceeds the real tax, so a refund
    assert year_2026["refund_eur"] > 0
    assert (
        df_years.loc[2027, "regular_month_net_eur"] > year_2026["regular_month_net_eur"]
    )


def test_build_salary_income_pays_refunds_next_june():
    list_months = [
        str(month) for month in pd.period_range("2026-11", "2027-07", freq="M")
    ]
    df_income, df_years = build_salary_income(SCHEDULE, 0.0, 14, 7, None, list_months)
    df_income = df_income.set_index("month")

    refund_2026 = df_years.set_index("year").loc[2026, "refund_eur"]
    assert df_income.loc["2027-06", "tax_refund_eur"] == pytest.approx(refund_2026)
    assert df_income["tax_refund_eur"].drop("2027-06").eq(0).all()
    assert df_income.index.tolist() == list_months
