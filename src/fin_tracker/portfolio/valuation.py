"""Current value of cash and investments across all accounts."""

import pandas as pd

from fin_tracker.config import (
    DEFAULT_ASSET_BUCKET,
    ISIN_TO_ASSET_BUCKET,
    SUB_ACCOUNT_OWNERSHIP_SHARE,
)
from fin_tracker.portfolio.holdings import compute_fifo_positions
from fin_tracker.portfolio.market_data import (
    get_eur_per_unit,
    get_latest_quote,
    resolve_ticker,
)
from fin_tracker.schema import compute_net_cash_eur


def compute_cash_balances(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Compute the current cash balance of every account and sub-account.

    BBVA and Revolut report a running balance, so the last one is used.
    Trade Republic has no balance column, so its cash is the sum of every
    cash flow (amount plus fees and taxes) in the extract.

    Args:
        df_transactions: Unified transactions dataframe, chronologically sorted.

    Returns:
        One row per (account, sub_account) with the balance in its own currency,
        in EUR at today's FX rate, and the share of it that is mine.
    """
    has_running_balance = df_transactions["balance"].notna()

    df_running_balances = (
        df_transactions[has_running_balance]
        .groupby(["account", "sub_account"], observed=True, dropna=False)
        .agg(
            currency=("currency", "last"),
            balance=("balance", "last"),
            last_movement_date=("date", "max"),
        )
        .reset_index()
    )

    df_tr = df_transactions[df_transactions["account"] == "trade_republic"]
    df_tr_cash = pd.DataFrame(
        [
            {
                "account": "trade_republic",
                "sub_account": "cash",
                "currency": "EUR",
                "balance": float(compute_net_cash_eur(df_tr).sum()),
                "last_movement_date": df_tr["date"].max(),
            }
        ]
    )

    df_cash_balances = pd.concat([df_running_balances, df_tr_cash], ignore_index=True)
    df_cash_balances["balance_eur"] = df_cash_balances["balance"] * df_cash_balances[
        "currency"
    ].map(get_eur_per_unit)
    df_cash_balances["ownership_share"] = (
        df_cash_balances["sub_account"].map(SUB_ACCOUNT_OWNERSHIP_SHARE).fillna(1.0)
    )
    df_cash_balances["my_balance_eur"] = (
        df_cash_balances["balance_eur"] * df_cash_balances["ownership_share"]
    )
    return df_cash_balances


def value_positions(df_positions: pd.DataFrame) -> pd.DataFrame:
    """Price open positions at their latest close in EUR.

    Positions without a yfinance price are kept with empty market columns so
    they are visible; add the ISIN to ``ISIN_TO_TICKER_OVERRIDE`` to fix them.

    Args:
        df_positions: Open positions from :func:`compute_fifo_positions`.

    Returns:
        Positions with ticker, asset bucket, latest price, market value and
        unrealized gain.
    """
    list_rows_quotes = []
    for asset_isin in df_positions["asset_isin"]:
        quote = get_latest_quote(resolve_ticker(asset_isin))
        list_rows_quotes.append(
            {
                "asset_isin": asset_isin,
                "ticker": quote.ticker if quote else None,
                "listing_currency": quote.listing_currency if quote else None,
                "price_date": quote.price_date if quote else pd.NaT,
                "last_price_eur": quote.price_eur if quote else float("nan"),
            }
        )

    df_valued_positions = df_positions.merge(
        pd.DataFrame(list_rows_quotes), on="asset_isin", how="left"
    )
    df_valued_positions["asset_bucket"] = (
        df_valued_positions["asset_isin"]
        .map(ISIN_TO_ASSET_BUCKET)
        .fillna(DEFAULT_ASSET_BUCKET)
    )
    df_valued_positions["market_value_eur"] = (
        df_valued_positions["shares"] * df_valued_positions["last_price_eur"]
    )
    df_valued_positions["unrealized_gain_eur"] = (
        df_valued_positions["market_value_eur"] - df_valued_positions["cost_basis_eur"]
    )
    df_valued_positions["unrealized_return"] = (
        df_valued_positions["unrealized_gain_eur"]
        / df_valued_positions["cost_basis_eur"]
    )
    return df_valued_positions.sort_values(
        "market_value_eur", ascending=False, ignore_index=True
    )


def compute_net_worth(df_transactions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Compute cash balances, valued investments and the overall net worth.

    Args:
        df_transactions: Unified transactions dataframe.

    Returns:
        Dictionary with:

        - ``df_cash_balances``: from :func:`compute_cash_balances`.
        - ``df_positions``: from :func:`value_positions`.
        - ``df_realized_gains``: from :func:`compute_fifo_positions`.
        - ``df_net_worth``: one row per account and asset type with its EUR value.
    """
    df_cash_balances = compute_cash_balances(df_transactions)
    df_open_positions, df_realized_gains = compute_fifo_positions(df_transactions)
    df_positions = value_positions(df_open_positions)

    df_cash_summary = (
        df_cash_balances.groupby("account", observed=True)["my_balance_eur"]
        .sum()
        .reset_index()
        .rename(columns={"my_balance_eur": "value_eur"})
        .assign(asset_type="cash")
    )
    df_investments_summary = pd.DataFrame(
        [
            {
                "account": "trade_republic",
                "asset_type": "investments",
                "value_eur": df_positions["market_value_eur"].sum(),
            }
        ]
    )
    df_net_worth = pd.concat(
        [df_cash_summary, df_investments_summary], ignore_index=True
    )[["account", "asset_type", "value_eur"]]

    return {
        "df_cash_balances": df_cash_balances,
        "df_positions": df_positions,
        "df_realized_gains": df_realized_gains,
        "df_net_worth": df_net_worth,
    }
