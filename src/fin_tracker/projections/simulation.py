"""Month-by-month projection of cash and investments for one scenario.

Every month: the net salary of that month's payslip (see ``payroll``) and
other income come in, expenses go out, a contribution moves from cash to
investments, cash earns its yield and investments their return. Expenses and
contributions change once a year (inflation, contribution growth). A Monte
Carlo variant draws random monthly investment returns to show how uncertain
the outcome is.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fin_tracker.config import DEFAULT_BONUS_MONTH
from fin_tracker.projections.payroll import SalaryStep, build_salary_income

MONTHS_PER_YEAR = 12
PERCENTILES = (10, 50, 90)


@dataclass(frozen=True)
class ScenarioParameters:
    """Everything a projection needs; all rates are annual and nominal.

    Attributes:
        horizon_years: Years to project.
        start_cash_eur: Liquid cash at the start.
        start_investments_eur: Market value of the investments at the start.
        salary_schedule: Gross salary and bonus changes, see ``SalaryStep``.
        salary_growth: Yearly raise after the last salary step.
        payments_per_year: 12 or 14 pays.
        bonus_month: Calendar month the bonus is paid in.
        retention_rate_override: Fixed IRPF withholding rate, None to compute it.
        monthly_other_income_eur: Other recurring income per month.
        monthly_expenses_eur: Spending per month.
        inflation: Yearly growth of expenses, also used for "today's euros".
        monthly_investment_eur: Contribution moved to investments every month.
        investment_growth: Yearly growth of the monthly contribution.
        cash_return: Yield on cash.
        investment_return: Expected return of the investments.
        investment_volatility: Yearly volatility of the investments (Monte Carlo).
    """

    horizon_years: int = 10
    start_cash_eur: float = 0.0
    start_investments_eur: float = 0.0
    salary_schedule: tuple[SalaryStep, ...] = field(default_factory=tuple)
    salary_growth: float = 0.0
    payments_per_year: int = 14
    bonus_month: int = DEFAULT_BONUS_MONTH
    retention_rate_override: float | None = None
    monthly_other_income_eur: float = 0.0
    monthly_expenses_eur: float = 0.0
    inflation: float = 0.0
    monthly_investment_eur: float = 0.0
    investment_growth: float = 0.0
    cash_return: float = 0.0
    investment_return: float = 0.0
    investment_volatility: float = 0.0

    @property
    def months(self) -> int:
        """Number of simulated months."""
        return self.horizon_years * MONTHS_PER_YEAR


def to_monthly_rate(annual_rate: float) -> float:
    """Monthly rate that compounds to ``annual_rate`` over a year."""
    return (1 + annual_rate) ** (1 / MONTHS_PER_YEAR) - 1


def build_monthly_flows(
    parameters: ScenarioParameters, start_month: pd.Period
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Salary, tax refund, other income, expenses and contribution of every month.

    Args:
        parameters: Scenario.
        start_month: First simulated month.

    Returns:
        A tuple ``(df_flows, df_payroll_years)``: one row per month with the
        flows in EUR, and the yearly payroll summary.
    """
    list_months = build_month_labels(parameters, start_month)
    df_income, df_payroll_years = build_salary_income(
        parameters.salary_schedule,
        parameters.salary_growth,
        parameters.payments_per_year,
        parameters.bonus_month,
        parameters.retention_rate_override,
        list_months,
    )
    series_year_index = pd.Series(np.arange(parameters.months) // MONTHS_PER_YEAR)
    df_flows = pd.DataFrame(
        {
            "salary_eur": df_income["salary_net_eur"],
            "tax_refund_eur": df_income["tax_refund_eur"],
            "other_income_eur": parameters.monthly_other_income_eur
            * (1 + parameters.inflation) ** series_year_index,
            "expenses_eur": parameters.monthly_expenses_eur
            * (1 + parameters.inflation) ** series_year_index,
            "contribution_eur": parameters.monthly_investment_eur
            * (1 + parameters.investment_growth) ** series_year_index,
        }
    )
    return df_flows, df_payroll_years


def simulate_paths(
    parameters: ScenarioParameters,
    df_flows: pd.DataFrame,
    array_monthly_returns: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Run the monthly loop for one or many investment return paths.

    Args:
        parameters: Scenario.
        df_flows: Monthly flows from :func:`build_monthly_flows`.
        array_monthly_returns: Investment returns, shape ``(paths, months)``.

    Returns:
        Arrays ``(cash, investments)`` of shape ``(paths, months)``, valued at
        the end of each month.
    """
    array_net_cash_flow = (
        df_flows["salary_eur"]
        + df_flows["tax_refund_eur"]
        + df_flows["other_income_eur"]
        - df_flows["expenses_eur"]
        - df_flows["contribution_eur"]
    ).to_numpy()
    array_contributions = df_flows["contribution_eur"].to_numpy()
    monthly_cash_return = to_monthly_rate(parameters.cash_return)

    paths_count = array_monthly_returns.shape[0]
    array_cash = np.empty((paths_count, parameters.months))
    array_investments = np.empty((paths_count, parameters.months))
    cash = np.full(paths_count, parameters.start_cash_eur)
    investments = np.full(paths_count, parameters.start_investments_eur)

    for month_index in range(parameters.months):
        # Balances earn their return, then the month's flows land at its end
        cash = cash * (1 + monthly_cash_return) + array_net_cash_flow[month_index]
        investments = (
            investments * (1 + array_monthly_returns[:, month_index])
            + array_contributions[month_index]
        )
        array_cash[:, month_index] = cash
        array_investments[:, month_index] = investments
    return array_cash, array_investments


def build_month_labels(
    parameters: ScenarioParameters, start_month: pd.Period
) -> list[str]:
    """``YYYY-MM`` labels of the simulated months, starting at ``start_month``."""
    return [str(start_month + offset) for offset in range(parameters.months)]


def simulate_scenario(
    parameters: ScenarioParameters, start_month: pd.Period
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deterministic projection: investments grow exactly at their expected return.

    Args:
        parameters: Scenario.
        start_month: First simulated month.

    Returns:
        A tuple ``(df_projection, df_payroll_years)``: one row per month with
        cash, investments, total, total in today's euros, invested principal
        and the month's flows; and the yearly payroll summary.
    """
    array_returns = np.full(
        (1, parameters.months), to_monthly_rate(parameters.investment_return)
    )
    df_flows, df_payroll_years = build_monthly_flows(parameters, start_month)
    array_cash, array_investments = simulate_paths(parameters, df_flows, array_returns)
    array_deflator = (1 + parameters.inflation) ** (
        (np.arange(parameters.months) + 1) / MONTHS_PER_YEAR
    )

    df_projection = pd.DataFrame(
        {
            "month": build_month_labels(parameters, start_month),
            "cash_eur": array_cash[0],
            "investments_eur": array_investments[0],
        }
    )
    df_projection["total_eur"] = (
        df_projection["cash_eur"] + df_projection["investments_eur"]
    )
    df_projection["total_real_eur"] = df_projection["total_eur"] / array_deflator
    df_projection["invested_principal_eur"] = (
        parameters.start_investments_eur + df_flows["contribution_eur"].cumsum()
    )
    return pd.concat([df_projection, df_flows], axis=1), df_payroll_years


def simulate_percentiles(
    parameters: ScenarioParameters,
    start_month: pd.Period,
    simulations: int = 1000,
    seed: int = 0,
) -> pd.DataFrame:
    """Monte Carlo spread of the total net worth.

    Monthly log returns are normal with a drift chosen so the *mean* growth
    equals the expected return; the median ends up slightly lower, as with
    real markets.

    Args:
        parameters: Scenario.
        start_month: First simulated month.
        simulations: Number of random paths.
        seed: Random seed, fixed so results are reproducible.

    Returns:
        One row per month with ``p10_eur``, ``p50_eur`` and ``p90_eur``.
    """
    monthly_volatility = parameters.investment_volatility / np.sqrt(MONTHS_PER_YEAR)
    monthly_drift = (
        np.log(1 + parameters.investment_return) / MONTHS_PER_YEAR
        - monthly_volatility**2 / 2
    )
    random_generator = np.random.default_rng(seed)
    array_log_returns = random_generator.normal(
        monthly_drift, monthly_volatility, size=(simulations, parameters.months)
    )
    df_flows, _ = build_monthly_flows(parameters, start_month)
    array_cash, array_investments = simulate_paths(
        parameters, df_flows, np.expm1(array_log_returns)
    )
    array_percentiles = np.percentile(
        array_cash + array_investments, PERCENTILES, axis=0
    )

    return pd.DataFrame(
        {
            "month": build_month_labels(parameters, start_month),
            **{
                f"p{percentile}_eur": array_percentiles[index]
                for index, percentile in enumerate(PERCENTILES)
            },
        }
    )


def summarize_projection(
    parameters: ScenarioParameters, df_projection: pd.DataFrame
) -> dict:
    """Headline numbers of a projection at its horizon.

    Args:
        parameters: Scenario.
        df_projection: Projection from :func:`simulate_scenario`.

    Returns:
        Final cash, investments, totals (nominal and in today's euros),
        contributions, gains from investment returns and the first month in
        which cash goes negative (None if it never does).
    """
    final_row = df_projection.iloc[-1]
    total_contributions = float(df_projection["contribution_eur"].sum())
    series_negative_months = df_projection.loc[df_projection["cash_eur"] < 0, "month"]
    return {
        "final_cash_eur": float(final_row["cash_eur"]),
        "final_investments_eur": float(final_row["investments_eur"]),
        "final_total_eur": float(final_row["total_eur"]),
        "final_total_real_eur": float(final_row["total_real_eur"]),
        "start_total_eur": parameters.start_cash_eur + parameters.start_investments_eur,
        "total_contributions_eur": total_contributions,
        "investment_gains_eur": float(final_row["investments_eur"])
        - parameters.start_investments_eur
        - total_contributions,
        "first_negative_cash_month": series_negative_months.iloc[0]
        if not series_negative_months.empty
        else None,
    }
