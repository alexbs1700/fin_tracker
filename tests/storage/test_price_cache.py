"""Tests for fin_tracker.storage.price_cache (yfinance is faked)."""

import pandas as pd
import pytest

from fin_tracker.storage import price_cache
from fin_tracker.storage.price_cache import (
    fetch_close_history,
    get_close_history,
    get_eur_per_unit_history,
    get_path_cache_file,
    read_cached_closes,
    to_daily,
)
from tests.conftest import FAKE_TODAY

pytestmark = pytest.mark.usefixtures("fake_yfinance")

START_DATE = pd.Timestamp("2026-10-01")


def test_fetch_close_history_returns_tz_naive_dates():
    series_closes = fetch_close_history("IE00TEST0001", START_DATE)
    assert series_closes.index.tz is None
    assert series_closes.index.min() == START_DATE
    assert (series_closes == 12.0).all()


def test_fetch_close_history_is_empty_for_unknown_ticker():
    assert fetch_close_history("NOPE", START_DATE).empty


def test_get_path_cache_file_replaces_unsafe_characters(tmp_path):
    assert get_path_cache_file("EURUSD=X", tmp_path).name == "EURUSD_X.csv"


def test_read_cached_closes_without_file_is_empty(tmp_path):
    assert read_cached_closes(tmp_path / "missing.csv").empty


def test_get_close_history_downloads_once_then_uses_cache(tmp_path, monkeypatch):
    list_fetch_calls = []
    original_fetch = price_cache.fetch_close_history

    def counting_fetch(ticker_symbol, start_date):
        list_fetch_calls.append(start_date)
        return original_fetch(ticker_symbol, start_date)

    monkeypatch.setattr(price_cache, "fetch_close_history", counting_fetch)

    series_first = get_close_history("IE00TEST0001", START_DATE, FAKE_TODAY, tmp_path)
    series_second = get_close_history("IE00TEST0001", START_DATE, FAKE_TODAY, tmp_path)

    assert len(list_fetch_calls) == 1
    assert series_first.equals(series_second)
    assert read_cached_closes(get_path_cache_file("IE00TEST0001", tmp_path)).equals(
        series_first
    )


def test_get_close_history_refetches_only_the_missing_tail(tmp_path, monkeypatch):
    get_close_history("IE00TEST0001", START_DATE, pd.Timestamp("2026-10-05"), tmp_path)
    # Keep only the first two cached days to simulate an old cache
    path_file = get_path_cache_file("IE00TEST0001", tmp_path)
    read_cached_closes(path_file).iloc[:2].rename_axis("date").to_csv(path_file)

    list_fetch_starts = []
    original_fetch = price_cache.fetch_close_history
    monkeypatch.setattr(
        price_cache,
        "fetch_close_history",
        lambda ticker, start: (
            list_fetch_starts.append(start) or original_fetch(ticker, start)
        ),
    )
    series_closes = get_close_history("IE00TEST0001", START_DATE, FAKE_TODAY, tmp_path)

    # Re-downloads from the last cached close minus the overlap, not from the start
    last_cached_close = pd.Timestamp("2026-10-02")
    assert list_fetch_starts == [
        last_cached_close - pd.Timedelta(days=price_cache.REFETCH_OVERLAP_DAYS)
    ]
    assert series_closes.index.max() == FAKE_TODAY


def test_to_daily_carries_values_over_weekends_and_backfills_start():
    series_values = pd.Series(
        [1.0, 2.0], index=pd.to_datetime(["2026-10-02", "2026-10-05"])
    )
    series_daily = to_daily(
        series_values, pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-06")
    )
    assert series_daily.tolist() == [1.0, 1.0, 1.0, 1.0, 2.0, 2.0]


def test_get_eur_per_unit_history():
    series_eur = get_eur_per_unit_history("EUR", START_DATE, FAKE_TODAY)
    series_usd = get_eur_per_unit_history("USD", START_DATE, FAKE_TODAY)
    series_pence = get_eur_per_unit_history("GBp", START_DATE, FAKE_TODAY)

    assert (series_eur == 1.0).all()
    assert series_usd.iloc[-1] == pytest.approx(0.8)
    assert series_pence.iloc[-1] == pytest.approx(1 / 0.8 / 100)
    assert len(series_usd) == (FAKE_TODAY - START_DATE).days + 1


def test_get_eur_per_unit_history_raises_without_fx_data():
    with pytest.raises(ValueError, match="XXX"):
        get_eur_per_unit_history("XXX", START_DATE, FAKE_TODAY)
