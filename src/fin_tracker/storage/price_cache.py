"""Daily close prices and FX rates from yfinance, cached as CSV files.

Each ticker is stored in ``data/processed/prices/<ticker>.csv``. Only the
missing tail is downloaded on later calls, so the app does not hit yfinance
on every page load.
"""

from pathlib import Path

import pandas as pd
import yfinance as yf

from fin_tracker.config import BASE_CURRENCY, PATH_PRICE_CACHE

# Days re-downloaded before the last cached date, in case the last close was revised
REFETCH_OVERLAP_DAYS = 5
# The first cached close may be a few days after start_date (weekends, holidays)
START_TOLERANCE_DAYS = 7


def fetch_close_history(ticker_symbol: str, start_date: pd.Timestamp) -> pd.Series:
    """Download daily closes from yfinance, not adjusted for dividends.

    Args:
        ticker_symbol: yfinance ticker.
        start_date: First date to download.

    Returns:
        Close prices indexed by tz-naive date, empty if yfinance has no data.
    """
    df_history = yf.Ticker(ticker_symbol).history(
        start=start_date.strftime("%Y-%m-%d"), auto_adjust=False
    )
    if df_history.empty:
        return pd.Series(dtype=float, name="close")
    series_close = df_history["Close"].rename("close")
    series_close.index = (
        pd.DatetimeIndex(series_close.index).tz_localize(None).normalize()
    )
    return series_close[~series_close.index.duplicated(keep="last")]


def get_path_cache_file(ticker_symbol: str, path_cache: Path) -> Path:
    """Return the CSV path of a ticker, with characters unsafe in file names replaced."""
    safe_name = "".join(
        character if character.isalnum() or character in ".-_" else "_"
        for character in ticker_symbol
    )
    return path_cache / f"{safe_name}.csv"


def read_cached_closes(path_file: Path) -> pd.Series:
    """Read a cached close series, or an empty series if there is no cache yet."""
    if not path_file.exists():
        return pd.Series(dtype=float, name="close")
    df_cached = pd.read_csv(path_file, parse_dates=["date"])
    return df_cached.set_index("date")["close"]


def get_close_history(
    ticker_symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    path_cache: Path | None = None,
) -> pd.Series:
    """Return daily closes between two dates, downloading only what is missing.

    Args:
        ticker_symbol: yfinance ticker.
        start_date: First date needed.
        end_date: Last date needed.
        path_cache: Cache folder, defaults to ``PATH_PRICE_CACHE``.

    Returns:
        Close prices on trading days between ``start_date`` and ``end_date``.
    """
    path_cache = path_cache or PATH_PRICE_CACHE
    path_file = get_path_cache_file(ticker_symbol, path_cache)
    series_cached = read_cached_closes(path_file)

    # Accept a one business day lag: today's close may not be published yet
    oldest_acceptable_close = pd.offsets.BDay().rollback(end_date) - pd.offsets.BDay(1)
    is_start_missing = series_cached.empty or series_cached.index.min() > (
        start_date + pd.Timedelta(days=START_TOLERANCE_DAYS)
    )
    is_end_missing = (
        series_cached.empty or series_cached.index.max() < oldest_acceptable_close
    )

    if is_start_missing or is_end_missing:
        fetch_from = (
            start_date
            if is_start_missing
            else series_cached.index.max() - pd.Timedelta(days=REFETCH_OVERLAP_DAYS)
        )
        series_fetched = fetch_close_history(ticker_symbol, fetch_from)
        series_cached = pd.concat([series_cached, series_fetched])
        series_cached = series_cached[
            ~series_cached.index.duplicated(keep="last")
        ].sort_index()
        path_cache.mkdir(parents=True, exist_ok=True)
        series_cached.rename_axis("date").rename("close").to_csv(path_file)

    return series_cached.loc[start_date:end_date]


def to_daily(
    series_values: pd.Series, start_date: pd.Timestamp, end_date: pd.Timestamp
) -> pd.Series:
    """Spread trading-day values over every calendar day, carrying the last value.

    Days before the first value take the first one, so a position bought on a
    weekend still gets a price.

    Args:
        series_values: Values indexed by date.
        start_date: First calendar day.
        end_date: Last calendar day.

    Returns:
        One value per calendar day.
    """
    index_days = pd.date_range(start_date, end_date, freq="D")
    return (
        series_values.reindex(series_values.index.union(index_days))
        .ffill()
        .bfill()[index_days]
    )


def get_eur_per_unit_history(
    currency: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    path_cache: Path | None = None,
) -> pd.Series:
    """Return the daily EUR value of one unit of ``currency``.

    Args:
        currency: ISO code, ``GBp`` (pence) supported.
        start_date: First calendar day.
        end_date: Last calendar day.
        path_cache: Cache folder, defaults to ``PATH_PRICE_CACHE``.

    Returns:
        EUR per unit for every calendar day.

    Raises:
        ValueError: If yfinance has no FX data for the currency.
    """
    index_days = pd.date_range(start_date, end_date, freq="D")
    if currency == BASE_CURRENCY:
        return pd.Series(1.0, index=index_days)
    if currency == "GBp":
        return get_eur_per_unit_history("GBP", start_date, end_date, path_cache) / 100

    # The pair is quoted as units of currency per EUR, invert it
    series_units_per_eur = get_close_history(
        f"{BASE_CURRENCY}{currency}=X", start_date, end_date, path_cache
    )
    if series_units_per_eur.empty:
        raise ValueError(f"No FX history for {BASE_CURRENCY}/{currency}")
    return 1 / to_daily(series_units_per_eur, start_date, end_date)
