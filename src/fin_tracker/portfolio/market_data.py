"""Market prices and FX rates from yfinance, converted to EUR."""

from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
import yfinance as yf

from fin_tracker.config import BASE_CURRENCY, ISIN_TO_TICKER_OVERRIDE

# Days of history requested so weekends and holidays still return a last close
PRICE_LOOKBACK_PERIOD = "5d"


@dataclass(frozen=True)
class Quote:
    """Last close of a listing, in its own currency and in EUR."""

    ticker: str
    listing_currency: str
    price: float
    price_eur: float
    price_date: pd.Timestamp


def resolve_ticker(asset_isin: str) -> str:
    """Return the yfinance ticker for an ISIN, using the override map first.

    Without an override the ISIN itself is passed to yfinance, which resolves
    it to some listing (not necessarily a EUR one).

    Args:
        asset_isin: ISIN of the asset.

    Returns:
        A yfinance ticker symbol.
    """
    return ISIN_TO_TICKER_OVERRIDE.get(asset_isin, asset_isin)


@lru_cache
def get_eur_per_unit(currency: str) -> float:
    """Return how many EUR one unit of ``currency`` is worth today.

    Args:
        currency: ISO currency code. ``GBp`` (pence, used for London listings)
            is supported.

    Returns:
        EUR value of one unit of the currency.

    Raises:
        ValueError: If yfinance returns no FX data.
    """
    if currency == BASE_CURRENCY:
        return 1.0
    if currency == "GBp":
        return get_eur_per_unit("GBP") / 100
    df_fx_history = yf.Ticker(f"{BASE_CURRENCY}{currency}=X").history(
        period=PRICE_LOOKBACK_PERIOD
    )
    if df_fx_history.empty:
        raise ValueError(f"No FX rate found for {BASE_CURRENCY}/{currency}")
    # The pair is quoted as units of currency per EUR, invert it
    return 1 / float(df_fx_history["Close"].iloc[-1])


@lru_cache
def get_latest_quote(ticker_symbol: str) -> Quote | None:
    """Fetch the last close of a ticker and convert it to EUR.

    Args:
        ticker_symbol: yfinance ticker symbol (or ISIN).

    Returns:
        The latest quote, or None if yfinance has no price for the ticker.
    """
    ticker = yf.Ticker(ticker_symbol)
    df_price_history = ticker.history(period=PRICE_LOOKBACK_PERIOD)
    if df_price_history.empty:
        return None

    listing_currency = ticker.fast_info["currency"]
    last_price = float(df_price_history["Close"].iloc[-1])
    return Quote(
        ticker=ticker.ticker,
        listing_currency=listing_currency,
        price=last_price,
        price_eur=last_price * get_eur_per_unit(listing_currency),
        price_date=df_price_history.index[-1],
    )
