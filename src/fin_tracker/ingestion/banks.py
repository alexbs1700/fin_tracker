"""Registry of the supported banks and how their extracts are read."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fin_tracker.config import (
    FILE_NAME_BBVA,
    FILE_NAME_REVOLUT,
    FILE_NAME_TRADE_REPUBLIC,
)
from fin_tracker.ingestion.bbva import normalize_bbva, read_bbva_raw
from fin_tracker.ingestion.revolut import normalize_revolut, read_revolut_raw
from fin_tracker.ingestion.trade_republic import (
    normalize_trade_republic,
    read_trade_republic_raw,
)


@dataclass(frozen=True)
class Bank:
    """How one bank's extract is named, read and normalized.

    Attributes:
        key: Identifier used in the unified ``account`` column and the API.
        label: Human name.
        file_name: Name of the extract inside ``data/raw``.
        read_raw: Reads the file into the bank's raw columns.
        normalize: Maps raw rows to the unified schema.
        required_columns: Raw columns the parser depends on.
        has_running_balance: Whether every row reports the balance after it.
    """

    key: str
    label: str
    file_name: str
    read_raw: Callable[[Path], pd.DataFrame]
    normalize: Callable[[pd.DataFrame], pd.DataFrame]
    required_columns: tuple[str, ...]
    has_running_balance: bool

    @property
    def extension(self) -> str:
        """File extension the extract must have, e.g. ``.csv``."""
        return Path(self.file_name).suffix


BANKS: dict[str, Bank] = {
    "bbva": Bank(
        key="bbva",
        label="BBVA",
        file_name=FILE_NAME_BBVA,
        read_raw=read_bbva_raw,
        normalize=normalize_bbva,
        required_columns=(
            "F.Valor", "Fecha", "Concepto", "Movimiento",
            "Importe", "Divisa", "Disponible", "Observaciones",
        ),
        has_running_balance=True,
    ),
    "revolut": Bank(
        key="revolut",
        label="Revolut",
        file_name=FILE_NAME_REVOLUT,
        read_raw=read_revolut_raw,
        normalize=normalize_revolut,
        required_columns=("date", "description", "category", "amount", "balance", "fees", "wallet"),
        has_running_balance=True,
    ),
    "trade_republic": Bank(
        key="trade_republic",
        label="Trade Republic",
        file_name=FILE_NAME_TRADE_REPUBLIC,
        read_raw=read_trade_republic_raw,
        normalize=normalize_trade_republic,
        required_columns=(
            "datetime", "date", "category", "type", "asset_class", "name", "symbol",
            "shares", "price", "amount", "fee", "tax", "currency", "original_amount",
            "original_currency", "fx_rate", "description", "transaction_id",
            "counterparty_name", "counterparty_iban", "payment_reference", "mcc_code",
        ),
        has_running_balance=False,
    ),
}  # fmt: skip


def get_bank(bank_key: str) -> Bank:
    """Return the registered bank, or raise ``KeyError`` with the valid keys."""
    if bank_key not in BANKS:
        raise KeyError(f"Unknown bank {bank_key!r}, expected one of {sorted(BANKS)}")
    return BANKS[bank_key]
