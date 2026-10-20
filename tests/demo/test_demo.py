"""Tests for fin_tracker.demo (prepare_demo, end to end over the real pipeline)."""

import pandas as pd
import pytest

from fin_tracker.demo import prepare_demo
from tests.demo.conftest import DEMO_END_DATE


@pytest.fixture(scope="module")
def demo_store(tmp_path_factory, request):
    monkeypatch = pytest.MonkeyPatch()
    request.addfinalizer(monkeypatch.undo)
    from fin_tracker.portfolio import market_data
    from fin_tracker.storage import price_cache

    monkeypatch.setattr(market_data.yf, "Ticker", market_data.yf.Ticker)
    monkeypatch.setattr(price_cache, "PATH_PRICE_CACHE", price_cache.PATH_PRICE_CACHE)
    request.addfinalizer(market_data.get_latest_quote.cache_clear)
    request.addfinalizer(market_data.get_eur_per_unit.cache_clear)
    return prepare_demo(tmp_path_factory.mktemp("demo"), DEMO_END_DATE)


def test_prepare_demo_isolates_every_path(demo_store):
    path_demo = demo_store.path_raw_data.parent
    assert demo_store.path_overrides.parent == path_demo
    assert demo_store.end_date == DEMO_END_DATE


def test_prepare_demo_wipes_previous_files(tmp_path, restore_market):
    (tmp_path / "stale.txt").write_text("old")
    prepare_demo(tmp_path, DEMO_END_DATE)
    assert not (tmp_path / "stale.txt").exists()


def test_demo_pairs_every_transfer_leg(demo_store):
    df_legs = demo_store.df_transactions.query("pair_transfer")
    assert len(df_legs) > 0
    assert df_legs["transfer_id"].notna().all()


def test_demo_categorizes_salary_rent_and_refund(demo_store):
    set_categories = set(demo_store.df_transactions["category"])
    assert {
        "Nómina",
        "Vivienda",
        "Devolución IRPF",
        "Cuenta conjunta",
        "Viajes",
    } <= set_categories


def test_demo_values_the_portfolio_offline(demo_store):
    df_net_worth = demo_store.dict_net_worth["df_net_worth"]
    value_investments = df_net_worth.loc[
        df_net_worth["asset_type"] == "investments", "value_eur"
    ].sum()
    assert value_investments > 10000
    assert len(demo_store.dict_net_worth["df_positions"]) == 4


def test_demo_histories_reach_the_end_date(demo_store):
    assert demo_store.df_net_worth_history["date"].max() == DEMO_END_DATE
    assert pd.notna(demo_store.df_portfolio_history["market_value_eur"]).any()
