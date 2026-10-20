"""Offline market for the demo: deterministic price paths instead of yfinance.

The demo funds have made-up ISINs, so yfinance knows nothing about them. Each
one gets a geometric Brownian motion path from a fixed origin date and seed,
so a given day always has the same close no matter when the demo is run.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fin_tracker.portfolio import market_data
from fin_tracker.storage import price_cache

DEMO_SEED = 17
# Paths start here so the close of a past day never changes between runs
PRICE_ORIGIN_DATE = pd.Timestamp("2023-01-02")
BUSINESS_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class DemoAsset:
    """A made-up listing and the parameters of its price path."""

    isin: str
    name: str
    asset_class: str
    start_price: float
    annual_drift: float
    annual_volatility: float


DEMO_ASSETS = {
    asset.isin: asset
    for asset in [
        DemoAsset("IE00DEMO0001", "Global Equity ETF (demo)", "FUND", 80.0, 0.08, 0.15),
        DemoAsset("IE00DEMO0002", "Emerging Markets ETF (demo)", "FUND", 30.0, 0.06, 0.18),
        DemoAsset("IE00DEMO0003", "Euro Govt Bond ETF (demo)", "FUND", 100.0, 0.025, 0.04),
        DemoAsset("ES00DEMO0004", "Dividend Utility SA (demo)", "STOCK", 12.0, 0.05, 0.20),
    ]
}  # fmt: skip

# FX pairs are quoted as units of currency per EUR, like yfinance's "EURxxx=X"
DEMO_FX_UNITS_PER_EUR = {"EURHUF=X": 400.0, "EURUSD=X": 1.10, "EURGBP=X": 0.85}


def build_price_history(isin: str, end_date: pd.Timestamp) -> pd.Series:
    """Daily closes of a demo asset from ``PRICE_ORIGIN_DATE`` to ``end_date``.

    Args:
        isin: ISIN of a demo asset.
        end_date: Last day of the path.

    Returns:
        Closes in EUR indexed by business day (tz-naive).

    Raises:
        KeyError: If the ISIN is not a demo asset.
    """
    asset = DEMO_ASSETS[isin]
    index_days = pd.bdate_range(PRICE_ORIGIN_DATE, end_date)
    # One generator per asset, so adding days only appends draws to the path
    rng = np.random.default_rng([DEMO_SEED, list(DEMO_ASSETS).index(isin)])
    daily_volatility = asset.annual_volatility / np.sqrt(BUSINESS_DAYS_PER_YEAR)
    # Lognormal drift correction so the expected yearly return is annual_drift
    daily_log_drift = (
        np.log1p(asset.annual_drift) / BUSINESS_DAYS_PER_YEAR - daily_volatility**2 / 2
    )
    array_log_returns = rng.normal(daily_log_drift, daily_volatility, len(index_days))
    array_log_returns[0] = 0.0
    return pd.Series(
        asset.start_price * np.exp(np.cumsum(array_log_returns)),
        index=index_days,
        name="close",
    ).round(4)


def get_price_on(isin: str, date: pd.Timestamp) -> float:
    """Close of a demo asset on ``date``, or the last one before it.

    Args:
        isin: ISIN of a demo asset.
        date: Any calendar day on or after ``PRICE_ORIGIN_DATE``.

    Returns:
        The close in EUR.
    """
    return float(build_price_history(isin, date).iloc[-1])


class DemoTicker:
    """Stand-in for ``yfinance.Ticker`` serving the demo assets and FX pairs.

    Unknown symbols return an empty history, as yfinance does.
    """

    def __init__(self, ticker_symbol: str, end_date: pd.Timestamp | None = None):
        self.ticker = ticker_symbol
        self.end_date = end_date or pd.Timestamp.today().normalize()
        self.fast_info = {"currency": self.get_currency()}

    def get_currency(self) -> str | None:
        """Listing currency: EUR for demo assets, the quote currency for FX pairs."""
        if self.ticker in DEMO_ASSETS:
            return "EUR"
        if self.ticker in DEMO_FX_UNITS_PER_EUR:
            return self.ticker[3:6]
        return None

    def history(
        self, period: str | None = None, start: str | None = None, **kwargs
    ) -> pd.DataFrame:
        """Daily closes from ``start`` (or the last week) to the end date, UTC indexed."""
        start_date = (
            pd.Timestamp(start) if start else self.end_date - pd.Timedelta(7, "D")
        )
        if self.ticker in DEMO_ASSETS:
            series_close = build_price_history(self.ticker, self.end_date)
        elif self.ticker in DEMO_FX_UNITS_PER_EUR:
            index_days = pd.bdate_range(PRICE_ORIGIN_DATE, self.end_date)
            series_close = pd.Series(
                DEMO_FX_UNITS_PER_EUR[self.ticker], index=index_days
            )
        else:
            return pd.DataFrame(columns=["Close"])
        series_close = series_close.loc[start_date:]
        return pd.DataFrame(
            {"Close": series_close.to_numpy()},
            index=series_close.index.tz_localize("UTC"),
        )


def install_demo_market(path_price_cache: Path) -> None:
    """Route every yfinance call of this process to ``DemoTicker``.

    The price cache moves to ``path_price_cache`` so demo closes never mix
    with the real cache in ``data/processed/prices``.

    Args:
        path_price_cache: Folder for the demo price cache.
    """
    # market_data and price_cache share the yfinance module object
    market_data.yf.Ticker = DemoTicker
    price_cache.PATH_PRICE_CACHE = path_price_cache
    market_data.get_eur_per_unit.cache_clear()
    market_data.get_latest_quote.cache_clear()
