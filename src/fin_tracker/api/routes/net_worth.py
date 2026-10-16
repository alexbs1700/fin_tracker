"""Net worth endpoints: current snapshot and daily history."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from fin_tracker.api.dependencies import (
    DateFrom,
    DateTo,
    Frequency,
    get_store,
    to_timestamp,
)
from fin_tracker.api.models import (
    AccountPoint,
    LiquidityPoint,
    MonthlyNetWorthStats,
    NetWorthSummary,
)
from fin_tracker.api.serialization import (
    dataframe_to_records,
    filter_date_range,
    resample_last,
)
from fin_tracker.api.store import FinanceDataStore
from fin_tracker.history import summarize_liquidity
from fin_tracker.history.net_worth import (
    ASSET_TYPE_CASH,
    ASSET_TYPE_INVESTMENTS,
    summarize_monthly_stats,
)

router = APIRouter(prefix="/api/net-worth", tags=["net worth"])
Store = Annotated[FinanceDataStore, Depends(get_store)]


@router.get("", response_model=NetWorthSummary)
def get_net_worth(store: Store) -> dict:
    """Current net worth with live prices, split into liquid cash and investments."""
    df_net_worth = store.dict_net_worth["df_net_worth"]
    series_value_by_type = df_net_worth.groupby("asset_type")["value_eur"].sum()
    cash_eur = float(series_value_by_type.get(ASSET_TYPE_CASH, 0.0))
    investments_eur = float(series_value_by_type.get(ASSET_TYPE_INVESTMENTS, 0.0))

    df_cash_wallets = store.dict_net_worth["df_cash_balances"][
        [
            "account",
            "sub_account",
            "currency",
            "balance",
            "balance_eur",
            "ownership_share",
            "my_balance_eur",
        ]
    ]
    return {
        "total_eur": cash_eur + investments_eur,
        "cash_eur": cash_eur,
        "investments_eur": investments_eur,
        "by_account": dataframe_to_records(df_net_worth.astype({"account": "string"})),
        "cash_wallets": dataframe_to_records(
            df_cash_wallets.astype({"account": "string"})
        ),
    }


@router.get("/history", response_model=list[LiquidityPoint])
def get_net_worth_history(
    store: Store,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    frequency: Frequency = "D",
) -> list[dict]:
    """Daily (or weekly / monthly) net worth split into cash and investments."""
    df_liquidity = filter_date_range(
        summarize_liquidity(store.df_net_worth_history),
        to_timestamp(date_from),
        to_timestamp(date_to),
    )
    return dataframe_to_records(resample_last(df_liquidity, frequency))


@router.get("/history/accounts", response_model=list[AccountPoint])
def get_net_worth_history_by_account(
    store: Store,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    frequency: Frequency = "D",
) -> list[dict]:
    """Value of every account and asset type over time."""
    df_history = filter_date_range(
        store.df_net_worth_history, to_timestamp(date_from), to_timestamp(date_to)
    )
    return dataframe_to_records(
        resample_last(df_history, frequency, ["account", "asset_type"])
    )


@router.get("/monthly-stats", response_model=list[MonthlyNetWorthStats])
def get_net_worth_monthly_stats(
    store: Store,
    value: Literal["total", "cash", "investments"] = "total",
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> list[dict]:
    """Monthly minimum, maximum, mean and median of the daily net worth."""
    df_liquidity = filter_date_range(
        summarize_liquidity(store.df_net_worth_history),
        to_timestamp(date_from),
        to_timestamp(date_to),
    )
    return dataframe_to_records(summarize_monthly_stats(df_liquidity, f"{value}_eur"))
