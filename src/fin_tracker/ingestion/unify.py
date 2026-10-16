"""Combine every bank extract into one transactions dataframe."""

from pathlib import Path

import pandas as pd

from fin_tracker.config import (
    FILE_NAME_BBVA,
    FILE_NAME_REVOLUT,
    FILE_NAME_TRADE_REPUBLIC,
    PATH_RAW_DATA,
)
from fin_tracker.ingestion.bbva import load_bbva
from fin_tracker.ingestion.keys import build_transaction_keys
from fin_tracker.ingestion.revolut import load_revolut
from fin_tracker.ingestion.trade_republic import load_trade_republic
from fin_tracker.schema import conform_to_schema


def load_all_transactions(path_raw_data: Path = PATH_RAW_DATA) -> pd.DataFrame:
    """Load BBVA, Revolut and Trade Republic into a single dataframe.

    Rows are sorted by date and timestamp with a stable sort, so same-day
    movements keep their original order and running balances stay consistent.

    Args:
        path_raw_data: Folder containing the raw extracts.

    Returns:
        All transactions in the unified schema.
    """
    list_df_accounts = [
        load_bbva(path_raw_data / FILE_NAME_BBVA),
        load_revolut(path_raw_data / FILE_NAME_REVOLUT),
        load_trade_republic(path_raw_data / FILE_NAME_TRADE_REPUBLIC),
    ]
    df_transactions = pd.concat(list_df_accounts, ignore_index=True).sort_values(
        ["date", "timestamp"], kind="stable", ignore_index=True
    )
    df_transactions["transaction_key"] = build_transaction_keys(df_transactions)
    return conform_to_schema(df_transactions)
