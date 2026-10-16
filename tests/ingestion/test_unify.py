"""Tests for fin_tracker.ingestion.unify."""

from fin_tracker.ingestion.unify import load_all_transactions
from fin_tracker.schema import UNIFIED_SCHEMA


def test_load_all_transactions_combines_and_sorts_every_account(path_raw_data):
    df_transactions = load_all_transactions(path_raw_data)

    assert df_transactions.columns.tolist() == list(UNIFIED_SCHEMA)
    assert df_transactions["account"].value_counts().to_dict() == {
        "trade_republic": 5,
        "revolut": 4,
        "bbva": 2,
    }
    assert df_transactions["date"].is_monotonic_increasing
