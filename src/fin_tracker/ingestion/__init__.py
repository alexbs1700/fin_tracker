"""Parsers that turn raw bank extracts into the unified transactions schema."""

from fin_tracker.ingestion.bbva import load_bbva
from fin_tracker.ingestion.revolut import load_revolut
from fin_tracker.ingestion.trade_republic import load_trade_republic
from fin_tracker.ingestion.unify import load_all_transactions

__all__ = ["load_all_transactions", "load_bbva", "load_revolut", "load_trade_republic"]
