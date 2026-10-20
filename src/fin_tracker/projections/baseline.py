"""Default scenario parameters estimated from my own transactions and holdings."""

import pandas as pd

from fin_tracker.config import (
    ASSET_BUCKET_EXPECTED_RETURN,
    ASSET_BUCKET_VOLATILITY,
    DEFAULT_BONUS_MONTH,
    DEFAULT_INFLATION,
    DEFAULT_SALARY_GROWTH,
    EXTRA_PAY_MONTHS,
    PROJECTION_LOOKBACK_MONTHS,
    TRADE_REPUBLIC_CASH_INTEREST_RATE,
)
from fin_tracker.schema import compute_net_cash_eur
from fin_tracker.taxes.spain import estimate_fixed_gross_from_net

SALARY_CATEGORY = "Nómina"
# Modelled by the payroll (June refunds), so it must not count as other income
TAX_REFUND_CATEGORY = "Devolución IRPF"
DEFAULT_PAYMENTS_PER_YEAR = 14


def get_complete_months(
    df_transactions: pd.DataFrame,
    today: pd.Timestamp,
    lookback_months: int = PROJECTION_LOOKBACK_MONTHS,
) -> pd.DataFrame:
    """Transactions of the last ``lookback_months`` complete months.

    The current month is left out because it is only partially observed.

    Args:
        df_transactions: Categorized transactions.
        today: Reference day.
        lookback_months: Number of complete months to keep.

    Returns:
        The transactions of those months.
    """
    current_month = today.to_period("M")
    series_month = df_transactions["date"].dt.to_period("M")
    return df_transactions[
        (series_month < current_month)
        & (series_month >= current_month - lookback_months)
    ]


def compute_monthly_averages(
    df_recent: pd.DataFrame, lookback_months: int = PROJECTION_LOOKBACK_MONTHS
) -> dict[str, float]:
    """Average monthly other income, expenses and investing.

    Salary and IRPF refunds are excluded on purpose: they come from the
    payroll model instead.

    Averages (not medians) on purpose: extra pays and holidays are part of
    the year, so they must be spread over every month.

    Args:
        df_recent: Categorized transactions of the complete lookback months.
        lookback_months: Number of months they cover.

    Returns:
        Monthly EUR amounts keyed by parameter name.
    """
    series_flow_type = df_recent["flow_type"].astype("string")
    is_salary = (series_flow_type == "income") & (
        df_recent["category"] == SALARY_CATEGORY
    )
    is_tax_refund = df_recent["category"] == TAX_REFUND_CATEGORY
    is_other_income = (series_flow_type == "income") & ~is_salary & ~is_tax_refund
    is_expense = series_flow_type == "expense"
    is_investment = series_flow_type == "investment"
    return {
        "monthly_other_income_eur": float(
            df_recent.loc[is_other_income, "amount_eur"].sum()
        )
        / lookback_months,
        "monthly_expenses_eur": -float(df_recent.loc[is_expense, "amount_eur"].sum())
        / lookback_months,
        # Buys minus sells, fees included
        "monthly_investment_eur": -float(
            compute_net_cash_eur(df_recent[is_investment]).sum()
        )
        / lookback_months,
    }


def estimate_current_salary(
    df_transactions: pd.DataFrame, today: pd.Timestamp
) -> dict | None:
    """Current yearly gross salary, inverted from the latest regular payslip.

    A regular payslip is a salary payment in a month without extra pay or
    bonus, so its net maps to the gross through the payroll rules.

    Args:
        df_transactions: Categorized transactions.
        today: Reference day; only complete months before it are used.

    Returns:
        A salary step as a dict, or None when no salary was found.
    """
    df_salary = df_transactions[
        (df_transactions["category"] == SALARY_CATEGORY)
        & (df_transactions["date"].dt.to_period("M") < today.to_period("M"))
    ]
    series_salary_by_month = df_salary.groupby(df_salary["date"].dt.to_period("M"))[
        "amount_eur"
    ].sum()
    set_irregular_months = {*EXTRA_PAY_MONTHS, DEFAULT_BONUS_MONTH}
    series_regular = series_salary_by_month[
        [
            month.month not in set_irregular_months
            for month in series_salary_by_month.index
        ]
    ]
    if series_regular.empty:
        return None
    last_month = series_regular.index[-1]
    return {
        "start_month": str(last_month),
        "gross_salary_eur": estimate_fixed_gross_from_net(
            float(series_regular.iloc[-1]), DEFAULT_PAYMENTS_PER_YEAR
        ),
        "gross_bonus_eur": 0.0,
    }


def compute_invested_salary_share(df_recent: pd.DataFrame) -> float:
    """Share of the net salary that went to investments over the lookback months.

    Args:
        df_recent: Categorized transactions of the complete lookback months.

    Returns:
        Invested amount divided by net salary received, 0 without salary.
    """
    series_flow_type = df_recent["flow_type"].astype("string")
    salary_eur = float(
        df_recent.loc[
            (series_flow_type == "income") & (df_recent["category"] == SALARY_CATEGORY),
            "amount_eur",
        ].sum()
    )
    invested_eur = -float(
        compute_net_cash_eur(df_recent[series_flow_type == "investment"]).sum()
    )
    return max(0.0, invested_eur / salary_eur) if salary_eur > 0 else 0.0


def compute_cash_return(df_cash_balances: pd.DataFrame) -> float:
    """Yield of my cash as a whole: only Trade Republic cash earns interest.

    Args:
        df_cash_balances: Current balances from ``compute_cash_balances``.

    Returns:
        Balance-weighted annual yield.
    """
    total_cash_eur = df_cash_balances["my_balance_eur"].sum()
    if total_cash_eur <= 0:
        return 0.0
    trade_republic_cash_eur = df_cash_balances.loc[
        df_cash_balances["account"] == "trade_republic", "my_balance_eur"
    ].sum()
    return float(
        trade_republic_cash_eur / total_cash_eur * TRADE_REPUBLIC_CASH_INTEREST_RATE
    )


def compute_portfolio_assumptions(df_positions: pd.DataFrame) -> dict[str, float]:
    """Expected return and volatility weighted by the current allocation.

    Volatility is a simple weighted average (it ignores diversification
    between buckets, so it errs on the prudent side).

    Args:
        df_positions: Valued positions with ``asset_bucket`` and ``market_value_eur``.

    Returns:
        ``investment_return`` and ``investment_volatility``.
    """
    series_value_by_bucket = df_positions.groupby("asset_bucket")[
        "market_value_eur"
    ].sum()
    total_value_eur = series_value_by_bucket.sum()
    if total_value_eur <= 0:
        return {
            "investment_return": ASSET_BUCKET_EXPECTED_RETURN["equity"],
            "investment_volatility": ASSET_BUCKET_VOLATILITY["equity"],
        }
    series_weights = series_value_by_bucket / total_value_eur
    return {
        "investment_return": float(
            (
                series_weights * series_weights.index.map(ASSET_BUCKET_EXPECTED_RETURN)
            ).sum()
        ),
        "investment_volatility": float(
            (series_weights * series_weights.index.map(ASSET_BUCKET_VOLATILITY)).sum()
        ),
    }


def estimate_baseline(
    df_transactions: pd.DataFrame,
    dict_net_worth: dict[str, pd.DataFrame],
    today: pd.Timestamp | None = None,
) -> dict:
    """Default scenario parameters from my data.

    Args:
        df_transactions: Categorized transactions.
        dict_net_worth: Output of ``compute_net_worth`` (current snapshot).
        today: Reference day, defaults to today.

    Returns:
        Starting balances, salary calendar, monthly flows and rates, keyed like
        :class:`~fin_tracker.projections.simulation.ScenarioParameters`
        (salary steps as plain dicts).
    """
    today = today or pd.Timestamp.today().normalize()
    df_cash_balances = dict_net_worth["df_cash_balances"]
    df_positions = dict_net_worth["df_positions"]
    df_recent = get_complete_months(df_transactions, today)
    return {
        "start_cash_eur": float(df_cash_balances["my_balance_eur"].sum()),
        "start_investments_eur": float(df_positions["market_value_eur"].sum()),
        **compute_monthly_averages(df_recent),
        "salary_schedule": [
            step for step in [estimate_current_salary(df_transactions, today)] if step
        ],
        "salary_growth": DEFAULT_SALARY_GROWTH,
        "payments_per_year": DEFAULT_PAYMENTS_PER_YEAR,
        "bonus_month": DEFAULT_BONUS_MONTH,
        "retention_rate_override": None,
        "inflation": DEFAULT_INFLATION,
        "investment_growth": 0.0,
        "investment_mode": "fixed",
        "investment_plan": [
            {
                "year": today.year,
                "salary_percent": round(compute_invested_salary_share(df_recent), 3),
            }
        ],
        "cash_return": compute_cash_return(df_cash_balances),
        **compute_portfolio_assumptions(df_positions),
    }
