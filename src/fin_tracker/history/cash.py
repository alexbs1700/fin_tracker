"""Daily cash balance of every account and wallet."""

import pandas as pd

from fin_tracker.config import SUB_ACCOUNT_OWNERSHIP_SHARE
from fin_tracker.schema import compute_net_cash_eur
from fin_tracker.storage.price_cache import get_eur_per_unit_history


def compute_running_balance_history(
    df_transactions: pd.DataFrame, end_date: pd.Timestamp
) -> pd.DataFrame:
    """Daily balance of the accounts that report a running balance (BBVA, Revolut).

    The balance of a day is the one after its last movement, carried forward
    over days without movements.

    Args:
        df_transactions: Unified transactions, chronologically sorted.
        end_date: Last day of the history.

    Returns:
        One row per (date, account, sub_account) with ``currency`` and ``balance``.
    """
    df_with_balance = df_transactions[df_transactions["balance"].notna()]
    list_df_histories = []

    for (account, sub_account), df_wallet in df_with_balance.groupby(
        ["account", "sub_account"], observed=True, dropna=False, sort=False
    ):
        series_daily_balance = df_wallet.groupby("date")["balance"].last()
        index_days = pd.date_range(series_daily_balance.index.min(), end_date, freq="D")
        list_df_histories.append(
            pd.DataFrame(
                {
                    "date": index_days,
                    "account": account,
                    "sub_account": sub_account,
                    "currency": df_wallet["currency"].iloc[-1],
                    "balance": series_daily_balance.reindex(index_days)
                    .ffill()
                    .to_numpy(dtype=float),
                }
            )
        )
    return pd.concat(list_df_histories, ignore_index=True)


def compute_trade_republic_cash_history(
    df_transactions: pd.DataFrame, end_date: pd.Timestamp
) -> pd.DataFrame:
    """Daily Trade Republic cash, rebuilt as the running sum of its net cash flows.

    Args:
        df_transactions: Unified transactions dataframe.
        end_date: Last day of the history.

    Returns:
        One row per date with ``currency`` and ``balance``.
    """
    df_tr = df_transactions[df_transactions["account"] == "trade_republic"]
    series_daily_flow = compute_net_cash_eur(df_tr).groupby(df_tr["date"]).sum()
    index_days = pd.date_range(series_daily_flow.index.min(), end_date, freq="D")
    return pd.DataFrame(
        {
            "date": index_days,
            "account": "trade_republic",
            "sub_account": "cash",
            "currency": "EUR",
            "balance": series_daily_flow.reindex(index_days, fill_value=0)
            .cumsum()
            .to_numpy(dtype=float),
        }
    )


def compute_cash_history(
    df_transactions: pd.DataFrame, end_date: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Daily cash of every account and wallet, converted to EUR at each day's rate.

    Args:
        df_transactions: Unified transactions, chronologically sorted.
        end_date: Last day of the history, defaults to today.

    Returns:
        One row per (date, account, sub_account) with ``balance``, ``balance_eur``
        and ``my_balance_eur`` (after the ownership share, e.g. 0 for the joint
        account).
    """
    end_date = end_date or pd.Timestamp.today().normalize()
    df_cash_history = pd.concat(
        [
            compute_running_balance_history(df_transactions, end_date),
            compute_trade_republic_cash_history(df_transactions, end_date),
        ],
        ignore_index=True,
    )

    df_cash_history["eur_per_unit"] = 1.0
    for currency in df_cash_history["currency"].unique():
        is_currency = df_cash_history["currency"] == currency
        series_eur_per_unit = get_eur_per_unit_history(
            currency, df_cash_history.loc[is_currency, "date"].min(), end_date
        )
        df_cash_history.loc[is_currency, "eur_per_unit"] = series_eur_per_unit.loc[
            df_cash_history.loc[is_currency, "date"]
        ].to_numpy()

    df_cash_history["balance_eur"] = (
        df_cash_history["balance"] * df_cash_history["eur_per_unit"]
    )
    df_cash_history["my_balance_eur"] = df_cash_history["balance_eur"] * (
        df_cash_history["sub_account"].map(SUB_ACCOUNT_OWNERSHIP_SHARE).fillna(1.0)
    )
    return df_cash_history.drop(columns="eur_per_unit")
