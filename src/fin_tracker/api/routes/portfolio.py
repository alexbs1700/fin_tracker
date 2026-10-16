"""Portfolio endpoints: positions, allocation, gains and value over time."""

from typing import Annotated, Literal

import pandas as pd
from fastapi import APIRouter, Depends

from fin_tracker.api.dependencies import (
    DateFrom,
    DateTo,
    Frequency,
    get_store,
    to_timestamp,
)
from fin_tracker.api.models import PortfolioPoint, PortfolioSummary
from fin_tracker.api.serialization import (
    dataframe_to_records,
    filter_date_range,
    resample_last,
)
from fin_tracker.api.store import FinanceDataStore

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
Store = Annotated[FinanceDataStore, Depends(get_store)]

DICT_BREAKDOWN_COLUMN = {"total": None, "bucket": "asset_bucket", "asset": "asset_name"}


@router.get("", response_model=PortfolioSummary)
def get_portfolio(store: Store) -> dict:
    """Open positions at the latest price, allocation by bucket and realized gains."""
    df_positions = store.dict_net_worth["df_positions"]
    df_realized_gains = store.dict_net_worth["df_realized_gains"]

    market_value_eur = float(df_positions["market_value_eur"].sum())
    cost_basis_eur = float(df_positions["cost_basis_eur"].sum())
    unrealized_gain_eur = market_value_eur - cost_basis_eur
    df_positions = df_positions.assign(
        weight=df_positions["market_value_eur"] / market_value_eur
        if market_value_eur
        else None
    )
    series_allocation = (
        df_positions.groupby("asset_bucket")["market_value_eur"].sum()
        / market_value_eur
        if market_value_eur
        else pd.Series(dtype=float)
    )
    return {
        "market_value_eur": market_value_eur,
        "cost_basis_eur": cost_basis_eur,
        "unrealized_gain_eur": unrealized_gain_eur,
        "unrealized_return": unrealized_gain_eur / cost_basis_eur
        if cost_basis_eur
        else None,
        "realized_gain_eur": float(df_realized_gains["realized_gain_eur"].sum())
        if not df_realized_gains.empty
        else 0.0,
        "allocation": series_allocation.to_dict(),
        "positions": dataframe_to_records(df_positions),
        "realized_gains": dataframe_to_records(df_realized_gains),
    }


@router.get("/history", response_model=list[PortfolioPoint])
def get_portfolio_history(
    store: Store,
    breakdown: Literal["total", "bucket", "asset"] = "total",
    date_from: DateFrom = None,
    date_to: DateTo = None,
    frequency: Frequency = "D",
) -> list[dict]:
    """Market value against FIFO cost basis over time, in total or per group."""
    df_history = filter_date_range(
        store.df_portfolio_history, to_timestamp(date_from), to_timestamp(date_to)
    )
    group_column = DICT_BREAKDOWN_COLUMN[breakdown]
    list_group_columns = ["date", group_column] if group_column else ["date"]
    df_points = (
        df_history.groupby(list_group_columns, as_index=False)
        .agg(
            cost_basis_eur=("cost_basis_eur", "sum"),
            market_value_eur=(
                "market_value_eur",
                lambda series: series.sum(min_count=1),
            ),
        )
        .rename(columns={group_column: "group"} if group_column else {})
    )
    return dataframe_to_records(
        resample_last(df_points, frequency, ["group"] if group_column else None)
    )
