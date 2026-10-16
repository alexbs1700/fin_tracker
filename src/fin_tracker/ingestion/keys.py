"""Stable identifiers for transactions that have no bank-provided id."""

import hashlib

import pandas as pd

# Columns that identify a movement in BBVA and Revolut extracts. The running
# balance makes otherwise identical same-day movements distinguishable.
KEY_COLUMNS = ["account", "sub_account", "date", "description", "amount", "balance"]
KEY_LENGTH = 16


def hash_key_parts(list_key_parts: list[str]) -> str:
    """Return a short sha1 hex digest of the joined key parts."""
    return hashlib.sha1("|".join(list_key_parts).encode("utf-8")).hexdigest()[
        :KEY_LENGTH
    ]


def build_transaction_keys(df_transactions: pd.DataFrame) -> pd.Series:
    """Build a key per transaction that stays the same when extracts are re-imported.

    Trade Republic rows reuse their ``transaction_id``. Other rows hash
    ``KEY_COLUMNS`` plus an occurrence counter, so exact duplicates (same day,
    amount, description and balance) still get distinct keys.

    Args:
        df_transactions: Transactions in the unified schema, in their final order.

    Returns:
        String series of keys aligned with ``df_transactions``.
    """
    df_key_parts = df_transactions[KEY_COLUMNS].astype("string").fillna("")
    series_occurrence = df_key_parts.groupby(KEY_COLUMNS, sort=False).cumcount()
    series_hashed_keys = pd.Series(
        [
            hash_key_parts([*row_parts, str(occurrence)])
            for row_parts, occurrence in zip(
                df_key_parts.itertuples(index=False, name=None),
                series_occurrence,
                strict=True,
            )
        ],
        index=df_transactions.index,
        dtype="string",
    )
    return df_transactions["transaction_id"].astype("string").fillna(series_hashed_keys)
