"""Daily value and FIFO cost basis of every investment."""

import pandas as pd

from fin_tracker.config import DEFAULT_ASSET_BUCKET, ISIN_TO_ASSET_BUCKET
from fin_tracker.portfolio.holdings import SHARES_TOLERANCE, compute_holdings_timeline
from fin_tracker.portfolio.market_data import get_latest_quote, resolve_ticker
from fin_tracker.storage.price_cache import (
    get_close_history,
    get_eur_per_unit_history,
    to_daily,
)

PORTFOLIO_HISTORY_COLUMNS = [
    "date",
    "asset_isin",
    "asset_name",
    "asset_bucket",
    "shares",
    "cost_basis_eur",
    "price_eur",
    "market_value_eur",
]


def get_daily_price_eur(
    asset_isin: str, start_date: pd.Timestamp, end_date: pd.Timestamp
) -> pd.Series | None:
    """Daily close of an asset in EUR, or None if yfinance has no price for it.

    Args:
        asset_isin: ISIN of the asset.
        start_date: First calendar day.
        end_date: Last calendar day.

    Returns:
        EUR price for every calendar day, or None.
    """
    ticker_symbol = resolve_ticker(asset_isin)
    quote = get_latest_quote(ticker_symbol)
    if quote is None:
        return None
    series_closes = get_close_history(ticker_symbol, start_date, end_date)
    if series_closes.empty:
        return None
    return to_daily(series_closes, start_date, end_date) * get_eur_per_unit_history(
        quote.listing_currency, start_date, end_date
    )


def compute_portfolio_history(
    df_transactions: pd.DataFrame, end_date: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Daily shares, cost basis and market value of every asset while it is held.

    Assets without a yfinance price keep their cost basis and an empty market
    value, so they are visible instead of silently valued at 0.

    Args:
        df_transactions: Unified transactions dataframe.
        end_date: Last day of the history, defaults to today.

    Returns:
        One row per (date, asset_isin) with ``PORTFOLIO_HISTORY_COLUMNS``.
    """
    end_date = end_date or pd.Timestamp.today().normalize()
    df_timeline = compute_holdings_timeline(df_transactions)
    series_asset_names = (
        df_transactions.dropna(subset=["asset_isin"])
        .groupby("asset_isin")["asset_name"]
        .last()
    )
    list_df_histories = []

    for asset_isin, df_asset_timeline in df_timeline.groupby("asset_isin"):
        index_days = pd.date_range(df_asset_timeline["date"].min(), end_date, freq="D")
        df_asset_history = (
            df_asset_timeline.set_index("date")[["shares", "cost_basis_eur"]]
            .reindex(index_days)
            .ffill()
            .rename_axis("date")
            .reset_index()
        )
        df_asset_history = df_asset_history[
            df_asset_history["shares"] > SHARES_TOLERANCE
        ]
        if df_asset_history.empty:
            continue

        series_price_eur = get_daily_price_eur(asset_isin, index_days[0], end_date)
        df_asset_history["price_eur"] = (
            series_price_eur.loc[df_asset_history["date"]].to_numpy()
            if series_price_eur is not None
            else float("nan")
        )
        df_asset_history["asset_isin"] = asset_isin
        df_asset_history["asset_name"] = series_asset_names.get(asset_isin)
        df_asset_history["asset_bucket"] = ISIN_TO_ASSET_BUCKET.get(
            asset_isin, DEFAULT_ASSET_BUCKET
        )
        df_asset_history["market_value_eur"] = (
            df_asset_history["shares"] * df_asset_history["price_eur"]
        )
        list_df_histories.append(df_asset_history[PORTFOLIO_HISTORY_COLUMNS])

    if not list_df_histories:
        return pd.DataFrame(columns=PORTFOLIO_HISTORY_COLUMNS)
    return pd.concat(list_df_histories, ignore_index=True)
