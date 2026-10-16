"""Daily net worth split into liquid cash and invested (variable) assets."""

import pandas as pd

from fin_tracker.history.cash import compute_cash_history
from fin_tracker.history.portfolio import compute_portfolio_history

ASSET_TYPE_CASH = "cash"
ASSET_TYPE_INVESTMENTS = "investments"


def compute_net_worth_history(
    df_transactions: pd.DataFrame, end_date: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Daily value of my cash per account plus my investments.

    Money moved to Trade Republic and spent on assets is not lost: it moves from
    ``cash`` to ``investments``. Only my share of each wallet counts (the joint
    account counts 0).

    Args:
        df_transactions: Unified transactions, chronologically sorted.
        end_date: Last day of the history, defaults to today.

    Returns:
        One row per (date, account, asset_type) with ``value_eur``.
    """
    end_date = end_date or pd.Timestamp.today().normalize()

    df_cash_by_account = (
        compute_cash_history(df_transactions, end_date)
        .groupby(["date", "account"], observed=True, as_index=False)["my_balance_eur"]
        .sum()
        .rename(columns={"my_balance_eur": "value_eur"})
        .assign(asset_type=ASSET_TYPE_CASH)
    )
    df_investments = (
        compute_portfolio_history(df_transactions, end_date)
        .groupby("date", as_index=False)["market_value_eur"]
        .sum(min_count=1)
        .rename(columns={"market_value_eur": "value_eur"})
        .assign(account="trade_republic", asset_type=ASSET_TYPE_INVESTMENTS)
    )
    return pd.concat([df_cash_by_account, df_investments], ignore_index=True)[
        ["date", "account", "asset_type", "value_eur"]
    ].astype({"account": "string"})


def summarize_liquidity(df_net_worth_history: pd.DataFrame) -> pd.DataFrame:
    """Pivot the net worth history into liquid cash, investments and total per day.

    Args:
        df_net_worth_history: Output of :func:`compute_net_worth_history`.

    Returns:
        One row per date with ``cash_eur``, ``investments_eur`` and ``total_eur``.
    """
    df_liquidity = (
        df_net_worth_history.pivot_table(
            index="date",
            columns="asset_type",
            values="value_eur",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reindex(columns=[ASSET_TYPE_CASH, ASSET_TYPE_INVESTMENTS], fill_value=0.0)
        .rename(
            columns={
                ASSET_TYPE_CASH: "cash_eur",
                ASSET_TYPE_INVESTMENTS: "investments_eur",
            }
        )
    )
    df_liquidity["total_eur"] = (
        df_liquidity["cash_eur"] + df_liquidity["investments_eur"]
    )
    return df_liquidity.rename_axis(columns=None).reset_index()


def summarize_monthly_stats(
    df_liquidity: pd.DataFrame, value_column: str
) -> pd.DataFrame:
    """Minimum, maximum, mean and median of a daily value within each month.

    The daily close of a balance swings with salary and rent days, so these
    monthly statistics describe the month better than its last day: the
    minimum is the money I surely had all month long.

    Args:
        df_liquidity: Daily rows from :func:`summarize_liquidity`.
        value_column: ``total_eur``, ``cash_eur`` or ``investments_eur``.

    Returns:
        One row per month (``YYYY-MM``) with ``min_eur``, ``max_eur``,
        ``mean_eur``, ``median_eur``, the dates of the min and max, the number
        of days observed and whether the month is still incomplete.
    """
    df_daily = df_liquidity[["date", value_column]].rename(
        columns={value_column: "value_eur"}
    )
    series_month = df_daily["date"].dt.to_period("M")
    df_grouped = df_daily.groupby(series_month)

    df_stats = df_grouped["value_eur"].agg(
        min_eur="min", max_eur="max", mean_eur="mean", median_eur="median"
    )
    df_stats["min_date"] = df_daily.loc[
        df_grouped["value_eur"].idxmin(), "date"
    ].to_numpy()
    df_stats["max_date"] = df_daily.loc[
        df_grouped["value_eur"].idxmax(), "date"
    ].to_numpy()
    df_stats["days"] = df_grouped.size()
    df_stats["is_partial"] = df_stats["days"] < df_stats.index.days_in_month
    return (
        df_stats.rename_axis("month")
        .reset_index()
        .assign(month=lambda df: df["month"].astype(str))
    )
