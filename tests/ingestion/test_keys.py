"""Tests for fin_tracker.ingestion.keys."""

from fin_tracker.ingestion.keys import (
    KEY_LENGTH,
    build_transaction_keys,
    hash_key_parts,
)
from tests.conftest import build_transactions


def test_hash_key_parts_is_deterministic_and_short():
    assert hash_key_parts(["a", "b"]) == hash_key_parts(["a", "b"])
    assert hash_key_parts(["a", "b"]) != hash_key_parts(["ab", ""])
    assert len(hash_key_parts(["a"])) == KEY_LENGTH


def test_build_transaction_keys_reuses_ids_and_separates_duplicates():
    dict_duplicate = {
        "date": "2026-01-01",
        "account": "bbva",
        "amount": -5.0,
        "description": "Bar",
    }
    df_transactions = build_transactions(
        [
            {**dict_duplicate, "transaction_key": None},
            {**dict_duplicate, "transaction_key": None},
            {"date": "2026-01-01", "account": "trade_republic", "amount": 1.0,
             "transaction_id": "tr-1", "transaction_key": None},
        ]
    )  # fmt: skip
    series_keys = build_transaction_keys(df_transactions)

    assert series_keys.iloc[0] != series_keys.iloc[1]
    assert series_keys.iloc[2] == "tr-1"
    # Same input, same keys: overrides survive re-imports
    assert series_keys.equals(build_transaction_keys(df_transactions))
