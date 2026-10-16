"""Tests for fin_tracker.api.store (yfinance is faked)."""

import pytest

from fin_tracker.categorization.overrides import load_overrides
from tests.conftest import FAKE_TODAY


def test_get_cached_builds_only_once(store):
    list_builds = []
    for _ in range(2):
        value = store.get_cached("answer", lambda: list_builds.append(1) or 42)
    assert value == 42
    assert len(list_builds) == 1


def test_properties_expose_every_dataset(store):
    assert len(store.df_raw_transactions) == 11
    assert "flow_type" in store.df_transactions.columns
    assert set(store.dict_net_worth) >= {"df_net_worth", "df_positions"}
    assert store.df_net_worth_history["date"].max() == FAKE_TODAY
    assert store.df_portfolio_history["date"].max() == FAKE_TODAY


def test_update_category_saves_override_and_refreshes(store):
    transaction_key = store.df_transactions["transaction_key"].iloc[0]
    series_updated = store.update_category(transaction_key, "Regalos", "expense")

    assert series_updated["category"] == "Regalos"
    assert series_updated["is_category_override"]
    assert load_overrides(store.path_overrides)["transaction_key"].tolist() == [
        transaction_key
    ]


def test_update_category_rejects_unknown_key(store):
    with pytest.raises(KeyError):
        store.update_category("missing", "Ocio", None)


def test_reload_clears_the_cache(store):
    df_first = store.df_raw_transactions
    store.reload()
    assert store.df_raw_transactions is not df_first
