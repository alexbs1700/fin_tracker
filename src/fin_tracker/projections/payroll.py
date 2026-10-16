"""Net salary of every projected month from a calendar of gross salary changes.

The calendar lists when the gross salary (and bonus) changes; after the last
change both grow by ``salary_growth`` every 12 months. Each month's payslip
is computed with Spanish payroll rules, and every June the previous year's
IRPF return settles the difference between what was withheld and the real
tax (usually a refund for a Madrid resident).
"""

from dataclasses import dataclass

import pandas as pd

from fin_tracker.config import EXTRA_PAY_MONTHS, TAX_REFUND_MONTH
from fin_tracker.taxes.spain import (
    SOCIAL_SECURITY_EMPLOYEE_RATE,
    SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR,
    compute_month_payroll,
    compute_retention_rate,
    compute_tax_liability,
)


@dataclass(frozen=True)
class SalaryStep:
    """Gross pay in force from ``start_month`` (``YYYY-MM``) until the next step."""

    start_month: str
    gross_salary_eur: float
    gross_bonus_eur: float = 0.0


def get_salary_at(
    month: pd.Period, salary_schedule: tuple[SalaryStep, ...], salary_growth: float
) -> tuple[float, float]:
    """Yearly fixed gross and bonus in force in ``month``.

    Before the first step the first step applies; after the last one, both
    amounts grow by ``salary_growth`` on each anniversary of that last change.

    Args:
        month: Calendar month.
        salary_schedule: Salary steps, in any order.
        salary_growth: Yearly raise after the last step.

    Returns:
        ``(fixed gross, bonus gross)`` per year, 0 without any step.
    """
    if not salary_schedule:
        return 0.0, 0.0
    list_steps = sorted(salary_schedule, key=lambda step: step.start_month)
    list_started = [
        step for step in list_steps if pd.Period(step.start_month, freq="M") <= month
    ]
    step = list_started[-1] if list_started else list_steps[0]
    if step is not list_steps[-1] or not list_started:
        return step.gross_salary_eur, step.gross_bonus_eur
    years_since_last_change = (month - pd.Period(step.start_month, freq="M")).n // 12
    growth_factor = (1 + salary_growth) ** years_since_last_change
    return step.gross_salary_eur * growth_factor, step.gross_bonus_eur * growth_factor


def build_payroll(
    salary_schedule: tuple[SalaryStep, ...],
    salary_growth: float,
    payments_per_year: int,
    bonus_month: int,
    retention_rate_override: float | None,
    first_year: int,
    last_year: int,
) -> pd.DataFrame:
    """Payslip of every month of whole calendar years.

    The withholding rate follows the salary in force (as when an employer
    recalculates it after a raise) unless a fixed override is given.

    Args:
        salary_schedule: Salary steps.
        salary_growth: Yearly raise after the last step.
        payments_per_year: 12 or 14.
        bonus_month: Calendar month of the bonus.
        retention_rate_override: Fixed withholding rate, or None to compute it.
        first_year: First calendar year.
        last_year: Last calendar year.

    Returns:
        One row per month with salary, rate, gross, Social Security,
        withholding and net.
    """
    list_rows = []
    for month in pd.period_range(f"{first_year}-01", f"{last_year}-12", freq="M"):
        fixed_gross_eur, bonus_gross_eur = get_salary_at(
            month, salary_schedule, salary_growth
        )
        retention_rate = (
            retention_rate_override
            if retention_rate_override is not None
            else compute_retention_rate(fixed_gross_eur + bonus_gross_eur)
        )
        list_rows.append(
            {
                "month": str(month),
                "year": month.year,
                "fixed_gross_eur": fixed_gross_eur,
                "bonus_gross_eur": bonus_gross_eur,
                "retention_rate": retention_rate,
                **compute_month_payroll(
                    month.month,
                    fixed_gross_eur,
                    bonus_gross_eur,
                    payments_per_year,
                    bonus_month,
                    EXTRA_PAY_MONTHS,
                    retention_rate,
                ),
            }
        )
    return pd.DataFrame(list_rows)


def describe_payslips(
    fixed_gross_eur: float,
    bonus_gross_eur: float,
    payments_per_year: int,
    retention_rate: float,
) -> dict[str, float]:
    """Net of a regular month, of each extra pay and of the bonus.

    Args:
        fixed_gross_eur: Yearly fixed gross.
        bonus_gross_eur: Yearly gross bonus.
        payments_per_year: 12 or 14.
        retention_rate: Withholding rate.

    Returns:
        ``regular_month_net_eur``, ``extra_pay_net_eur`` (0 with 12 pays) and
        ``bonus_net_eur``.
    """
    regular_month = compute_month_payroll(
        1, fixed_gross_eur, 0.0, payments_per_year, 0, (), retention_rate
    )
    pay_eur = fixed_gross_eur / payments_per_year
    regular_base_eur = pay_eur * (1 + (payments_per_year - 12) / 12)
    bonus_social_security_eur = SOCIAL_SECURITY_EMPLOYEE_RATE * (
        min(regular_base_eur + bonus_gross_eur, SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR)
        - min(regular_base_eur, SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR)
    )
    return {
        "regular_month_net_eur": regular_month["net_eur"],
        # No Social Security is charged on the extra pay itself
        "extra_pay_net_eur": pay_eur * (1 - retention_rate)
        if payments_per_year > 12
        else 0.0,
        "bonus_net_eur": bonus_gross_eur * (1 - retention_rate)
        - bonus_social_security_eur,
    }


def summarize_payroll_years(
    df_payroll: pd.DataFrame, payments_per_year: int
) -> pd.DataFrame:
    """Yearly totals, the real IRPF and the refund (or payment) settled next June.

    Args:
        df_payroll: Output of :func:`build_payroll`.
        payments_per_year: 12 or 14.

    Returns:
        One row per year with gross, Social Security, withholding, net, real
        tax, ``refund_eur`` (positive = Hacienda pays me) and the payslips of
        the salary in force at year end.
    """
    df_years = df_payroll.groupby("year", as_index=False).agg(
        gross_eur=("gross_eur", "sum"),
        social_security_eur=("social_security_eur", "sum"),
        retention_eur=("retention_eur", "sum"),
        net_eur=("net_eur", "sum"),
    )
    df_years["tax_liability_eur"] = [
        compute_tax_liability(row.gross_eur, row.social_security_eur)
        for row in df_years.itertuples()
    ]
    df_years["refund_eur"] = df_years["retention_eur"] - df_years["tax_liability_eur"]

    df_year_end = df_payroll.groupby("year").last()
    df_payslips = pd.DataFrame(
        [
            {
                "year": year,
                "retention_rate": row.retention_rate,
                **describe_payslips(
                    row.fixed_gross_eur,
                    row.bonus_gross_eur,
                    payments_per_year,
                    row.retention_rate,
                ),
            }
            for year, row in df_year_end.iterrows()
        ]
    )
    return df_years.merge(df_payslips, on="year")


def build_salary_income(
    salary_schedule: tuple[SalaryStep, ...],
    salary_growth: float,
    payments_per_year: int,
    bonus_month: int,
    retention_rate_override: float | None,
    list_months: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Net salary and tax refunds landing in each projected month.

    Whole calendar years are computed (also the months before the projection
    starts) so the first year's refund reflects a full year of payslips.

    Args:
        salary_schedule: Salary steps.
        salary_growth: Yearly raise after the last step.
        payments_per_year: 12 or 14.
        bonus_month: Calendar month of the bonus.
        retention_rate_override: Fixed withholding rate, or None.
        list_months: Projected months, ``YYYY-MM``, consecutive.

    Returns:
        A tuple ``(df_income, df_years)``: per projected month the payslip net
        and the refund, and the yearly payroll summary.
    """
    first_year = int(list_months[0][:4])
    last_year = int(list_months[-1][:4])
    df_payroll = build_payroll(
        salary_schedule,
        salary_growth,
        payments_per_year,
        bonus_month,
        retention_rate_override,
        first_year,
        last_year,
    )
    df_years = summarize_payroll_years(df_payroll, payments_per_year)

    # Year Y's return settles in June of Y + 1
    dict_refund_by_month = {
        f"{year + 1}-{TAX_REFUND_MONTH:02d}": refund_eur
        for year, refund_eur in zip(
            df_years["year"], df_years["refund_eur"], strict=True
        )
    }
    df_income = (
        df_payroll.set_index("month")
        .loc[list_months, ["gross_eur", "net_eur"]]
        .rename(columns={"gross_eur": "salary_gross_eur", "net_eur": "salary_net_eur"})
        .reset_index()
    )
    df_income["tax_refund_eur"] = (
        df_income["month"].map(dict_refund_by_month).fillna(0.0)
    )
    return df_income, df_years
