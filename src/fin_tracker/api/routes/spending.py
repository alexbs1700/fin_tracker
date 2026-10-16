"""Spending and monthly cash flow endpoints.

Only ``expense`` rows count as spending and only ``income`` /
``investment_income`` as income, so internal transfers and investing never
inflate either side.
"""

from typing import Annotated, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Query

from fin_tracker.api.dependencies import DateFrom, DateTo, get_store, to_timestamp
from fin_tracker.api.models import MonthlyCashFlow, SpendingRow
from fin_tracker.api.serialization import dataframe_to_records, filter_date_range
from fin_tracker.api.store import FinanceDataStore
from fin_tracker.schema import compute_net_cash_eur

router = APIRouter(prefix="/api", tags=["spending"])
Store = Annotated[FinanceDataStore, Depends(get_store)]

INCOME_FLOW_TYPES = ["income", "investment_income"]
# BBVA puts the payee of transfers and Bizums in transaction_type, not description
GENERIC_DESCRIPTIONS = ["Transferencia realizada", "Transferencia recibida", "Bizum"]
DICT_GROUP_COLUMNS = {
    "category": ["category"],
    "month": ["month"],
    "month_category": ["month", "category"],
    "merchant": ["merchant"],
}


def add_month(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Add a ``YYYY-MM`` month column."""
    return df_transactions.assign(month=df_transactions["date"].dt.strftime("%Y-%m"))


def get_merchant(df_transactions: pd.DataFrame) -> pd.Series:
    """Best payee label: the description, or ``transaction_type`` when it is generic.

    Args:
        df_transactions: Transactions in the unified schema.

    Returns:
        Merchant / payee name per row.
    """
    series_description = df_transactions["description"].fillna("").str.strip()
    is_generic = series_description.isin(GENERIC_DESCRIPTIONS)
    return series_description.mask(
        is_generic, df_transactions["transaction_type"].fillna(series_description)
    )


def summarize_spending(
    df_transactions: pd.DataFrame, group_by: str, limit: int | None = None
) -> pd.DataFrame:
    """Spending (positive EUR) per group, biggest first.

    Args:
        df_transactions: Categorized transactions.
        group_by: Key of ``DICT_GROUP_COLUMNS``.
        limit: Maximum number of rows.

    Returns:
        Rows with the group columns, ``spent_eur`` and ``transactions``.
    """
    df_expenses = add_month(
        df_transactions[df_transactions["flow_type"] == "expense"]
    ).assign(merchant=get_merchant)
    list_group_columns = DICT_GROUP_COLUMNS[group_by]
    df_summary = (
        df_expenses.groupby(list_group_columns, as_index=False)
        .agg(spent_eur=("amount_eur", "sum"), transactions=("amount_eur", "size"))
        .assign(spent_eur=lambda df: -df["spent_eur"])
    )
    # Months stay chronological, everything else sorts by spending
    if group_by.startswith("month"):
        df_summary = df_summary.sort_values(
            ["month", "spent_eur"], ascending=[True, False]
        )
    else:
        df_summary = df_summary.sort_values("spent_eur", ascending=False)
    return df_summary.head(limit) if limit else df_summary


def summarize_monthly_cash_flow(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Income, spending, savings, savings rate and net investing per month.

    Args:
        df_transactions: Categorized transactions.

    Returns:
        One row per month, oldest first.
    """
    df_with_month = add_month(df_transactions)
    series_flow_type = df_with_month["flow_type"].astype("string")
    df_monthly = (
        pd.DataFrame(
            {
                "income_eur": df_with_month["amount_eur"].where(
                    series_flow_type.isin(INCOME_FLOW_TYPES), 0.0
                ),
                "expenses_eur": -df_with_month["amount_eur"].where(
                    series_flow_type == "expense", 0.0
                ),
                # Buys are negative cash flows: money moved into investments
                "invested_eur": -compute_net_cash_eur(df_with_month).where(
                    series_flow_type == "investment", 0.0
                ),
                "month": df_with_month["month"],
            }
        )
        .groupby("month", as_index=False)
        .sum()
    )
    df_monthly["savings_eur"] = df_monthly["income_eur"] - df_monthly["expenses_eur"]
    df_monthly["savings_rate"] = (
        df_monthly["savings_eur"] / df_monthly["income_eur"]
    ).where(df_monthly["income_eur"] > 0)
    return df_monthly


@router.get("/spending/summary", response_model=list[SpendingRow])
def get_spending_summary(
    store: Store,
    group_by: Literal["category", "month", "month_category", "merchant"] = "category",
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> list[dict]:
    """Spending aggregated by category, month, month and category, or merchant."""
    df_transactions = filter_date_range(
        store.df_transactions, to_timestamp(date_from), to_timestamp(date_to)
    )
    return dataframe_to_records(summarize_spending(df_transactions, group_by, limit))


@router.get("/cash-flow/monthly", response_model=list[MonthlyCashFlow])
def get_monthly_cash_flow(
    store: Store, date_from: DateFrom = None, date_to: DateTo = None
) -> list[dict]:
    """Monthly income, spending, savings rate and money invested."""
    df_transactions = filter_date_range(
        store.df_transactions, to_timestamp(date_from), to_timestamp(date_to)
    )
    return dataframe_to_records(summarize_monthly_cash_flow(df_transactions))
