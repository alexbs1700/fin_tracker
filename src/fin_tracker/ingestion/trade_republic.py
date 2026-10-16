"""Trade Republic extract parser: a tidy csv already in EUR."""

from pathlib import Path

import pandas as pd

from fin_tracker.config import FILE_NAME_TRADE_REPUBLIC, PATH_RAW_DATA
from fin_tracker.schema import conform_to_schema


def read_trade_republic_raw(
    path_file: Path = PATH_RAW_DATA / FILE_NAME_TRADE_REPUBLIC,
) -> pd.DataFrame:
    """Read the raw Trade Republic csv extract.

    Args:
        path_file: Path to the Trade Republic csv extract.

    Returns:
        Raw Trade Republic movements.
    """
    return pd.read_csv(path_file)


def normalize_trade_republic(df_tr_raw: pd.DataFrame) -> pd.DataFrame:
    """Map raw Trade Republic movements to the unified schema.

    ``amount`` excludes ``fee`` and ``tax``, which are reported as separate
    negative values. ``account_type`` is always ``DEFAULT`` so it is dropped.

    Args:
        df_tr_raw: Output of :func:`read_trade_republic_raw`.

    Returns:
        Trade Republic transactions in the unified schema.
    """
    # "name" holds the asset for trades and the merchant / counterparty for cash movements
    is_asset = df_tr_raw["asset_class"].notna()

    df_tr = pd.DataFrame(
        {
            "account": "trade_republic",
            "sub_account": df_tr_raw["category"].str.lower(),
            "transaction_id": df_tr_raw["transaction_id"],
            "date": pd.to_datetime(df_tr_raw["date"], format="%Y-%m-%d"),
            "timestamp": pd.to_datetime(
                df_tr_raw["datetime"], format="ISO8601", utc=True
            ),
            "transaction_type": df_tr_raw["type"],
            "description": df_tr_raw["description"],
            "counterparty_name": df_tr_raw["counterparty_name"].fillna(
                df_tr_raw["name"].where(~is_asset)
            ),
            "counterparty_iban": df_tr_raw["counterparty_iban"],
            "payment_reference": df_tr_raw["payment_reference"],
            "mcc_code": df_tr_raw["mcc_code"],
            "asset_class": df_tr_raw["asset_class"],
            "asset_name": df_tr_raw["name"].where(is_asset),
            "asset_isin": df_tr_raw["symbol"],
            "shares": df_tr_raw["shares"],
            "price": df_tr_raw["price"],
            "amount": df_tr_raw["amount"],
            "currency": df_tr_raw["currency"],
            "amount_eur": df_tr_raw["amount"],
            "fee": df_tr_raw["fee"],
            "fee_eur": df_tr_raw["fee"],
            "tax": df_tr_raw["tax"],
            "tax_eur": df_tr_raw["tax"],
            "original_amount": df_tr_raw["original_amount"],
            "original_currency": df_tr_raw["original_currency"],
            "fx_rate": df_tr_raw["fx_rate"],
        }
    )
    return conform_to_schema(df_tr)


def load_trade_republic(
    path_file: Path = PATH_RAW_DATA / FILE_NAME_TRADE_REPUBLIC,
) -> pd.DataFrame:
    """Read and normalize the Trade Republic extract.

    Args:
        path_file: Path to the Trade Republic csv extract.

    Returns:
        Trade Republic transactions in the unified schema.
    """
    return normalize_trade_republic(read_trade_republic_raw(path_file))
