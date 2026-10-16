"""Shared fixtures: synthetic bank extracts and a fake yfinance.

All data here is made up. Never paste real rows from data/raw.
"""

from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from fin_tracker.config import (
    FILE_NAME_BBVA,
    FILE_NAME_REVOLUT,
    FILE_NAME_TRADE_REPUBLIC,
)
from fin_tracker.portfolio import market_data

# ---------------------------------------------------------------------------
# Synthetic raw extracts
# ---------------------------------------------------------------------------

BBVA_HEADER = [
    None,
    "F.Valor",
    "Fecha",
    "Concepto",
    "Movimiento",
    "Importe",
    "Divisa",
    "Disponible",
    "Divisa",
    "Observaciones",
]
# Newest first, as BBVA exports them
BBVA_ROWS = [
    [None, "01/02/2026", "02/02/2026", "Super  market", "Pago con tarjeta", -20.0, "EUR", 980.0, "EUR", "1111   SUPER MARKET  MADRID"],
    [None, "01/01/2026", "01/01/2026", "Nomina", "Abono de nómina", 1000.0, "EUR", 1000.0, "EUR", "EMPRESA SL"],
]  # fmt: skip

REVOLUT_EUR_HEADER = (
    'Fecha,Descripción,Categoría,"Entradas/salidas de dinero",Saldo,'
    '"Impuestos retenidos","Otros impuestos",Comisiones'
)
REVOLUT_FX_HEADER = (
    "Fecha,Descripción,Categoría,"
    '"Entradas/salidas de dinero","Entradas/salidas de dinero",Saldo,Saldo,'
    '"Impuestos retenidos","Impuestos retenidos","Otros impuestos","Otros impuestos",'
    "Comisiones,Comisiones"
)
REVOLUT_LINES = [
    '"Cuentas corrientes Resúmenes",,,,,,,,',
    ",,,,,,,,",
    '"Cuenta personal (EUR)",,,,,,,,',
    ',,"Saldo de cierre","91,01€",,,,,',
    "---------,,,,,,,,",
    '"Cuentas corrientes Estado de transacciones",,,,,,,,',
    ",,,,,,,,",
    '"Cuenta personal (EUR)",,,,,,,,',
    ",,,,,,,,",
    '"Extracto de transacción",,,,,,,,',
    REVOLUT_EUR_HEADER,
    '"8 jul 2025","Top up",Recargar,"100,00€","100,00€","0,00€","0,00€","0,00€"',
    '"7 sept 2025","Premium plan",Comercio,"-8,99€","91,01€","0,00€","0,00€","8,99€"',
    'Total,,,"91,01€",,"0,00€","0,00€","8,99€"',
    ",,,,,,,,",
    "---------,,,,,,,,",
    '"Cuenta personal (HUF)",,,,,,,,',
    ",,,,,,,,",
    '"Extracto de transacción",,,,,,,,',
    REVOLUT_FX_HEADER,
    '"5 ago 2026","Exchange",Cambio,"4.000,00 HUF","10,00€","4.000,00 HUF","10,00€",'
    '"0,00 HUF","0,00€","0,00 HUF","0,00€","0,00 HUF","0,00€"',
    'Total,,,"4.000,00 HUF",,,,,,,,,',
    ",,,,,,,,",
    '"Cuenta Conjunta (EUR)",,,,,,,,',
    ",,,,,,,,",
    '"Extracto de transacción",,,,,,,,',
    REVOLUT_EUR_HEADER,
    '"3 oct 2026","Transfer in",Otras,"50,00€","50,00€","0,00€","0,00€","0,00€"',
    'Total,,,"50,00€",,"0,00€","0,00€","0,00€"',
    ",,,,,,,,",
    '"Round-Up (EUR)",,,,,,,,',
    ",,,,,,,,",
    '"Extracto de transacción",,,,,,,,',
    "---------,,,,,,,,",
]

TR_ROWS = [
    {"datetime": "2026-01-01T09:00:00Z", "category": "CASH", "type": "CUSTOMER_INPAYMENT", "amount": 1000.0, "description": "Top up"},
    {"datetime": "2026-01-02T10:00:00Z", "category": "TRADING", "type": "BUY", "asset_class": "FUND", "name": "Test ETF", "symbol": "IE00TEST0001", "shares": 10.0, "price": 10.0, "amount": -100.0, "fee": -1.0, "description": "Buy trade"},
    {"datetime": "2026-02-01T10:00:00Z", "category": "TRADING", "type": "SELL", "asset_class": "FUND", "name": "Test ETF", "symbol": "IE00TEST0001", "shares": -4.0, "price": 15.0, "amount": 60.0, "fee": -1.0, "description": "Sell trade"},
    {"datetime": "2026-03-01T10:00:00Z", "category": "CASH", "type": "DIVIDEND", "asset_class": "FUND", "name": "Test ETF", "symbol": "IE00TEST0001", "shares": 6.0, "amount": 2.0, "tax": -0.5, "description": "Cash Dividend"},
    {"datetime": "2026-03-05T10:00:00Z", "category": "CASH", "type": "CARD_TRANSACTION", "name": "SHOP", "amount": -50.0, "mcc_code": 5411, "description": "SHOP"},
]  # fmt: skip
TR_COLUMNS = [
    "datetime", "date", "account_type", "category", "type", "asset_class", "name",
    "symbol", "shares", "price", "amount", "fee", "tax", "currency", "original_amount",
    "original_currency", "fx_rate", "description", "transaction_id", "counterparty_name",
    "counterparty_iban", "payment_reference", "mcc_code",
]  # fmt: skip
# 1000 - 100 - 1 + 60 - 1 + 2 - 0.5 - 50
TR_EXPECTED_CASH_EUR = 909.5


def write_bbva_extract(path_file: Path) -> None:
    """Write a BBVA-like xlsx: 4 title rows, then header and rows."""
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(["Últimos movimientos"])
    worksheet.append(["Cuenta"])
    worksheet.append(["Periodo"])
    worksheet.append(["-"])
    worksheet.append(BBVA_HEADER)
    for row in BBVA_ROWS:
        worksheet.append(row)
    workbook.save(path_file)


def write_revolut_extract(path_file: Path) -> None:
    """Write a Revolut-like csv with EUR, HUF, joint and empty wallets."""
    path_file.write_text("\n".join(REVOLUT_LINES), encoding="utf-8")


def write_trade_republic_extract(path_file: Path) -> None:
    """Write a Trade Republic-like csv with cash movements and trades."""
    df_tr_raw = pd.DataFrame(TR_ROWS).reindex(columns=TR_COLUMNS)
    df_tr_raw["date"] = df_tr_raw["datetime"].str[:10]
    df_tr_raw["account_type"] = "DEFAULT"
    df_tr_raw["currency"] = "EUR"
    df_tr_raw["transaction_id"] = [f"id-{index}" for index in range(len(df_tr_raw))]
    df_tr_raw.to_csv(path_file, index=False)


@pytest.fixture
def path_raw_data(tmp_path: Path) -> Path:
    """Folder with synthetic BBVA, Revolut and Trade Republic extracts."""
    write_bbva_extract(tmp_path / FILE_NAME_BBVA)
    write_revolut_extract(tmp_path / FILE_NAME_REVOLUT)
    write_trade_republic_extract(tmp_path / FILE_NAME_TRADE_REPUBLIC)
    return tmp_path


# ---------------------------------------------------------------------------
# Fake yfinance
# ---------------------------------------------------------------------------

# Last close per ticker and its listing currency. FX pairs are units per EUR.
FAKE_MARKET = {
    "EURUSD=X": (1.25, "USD"),
    "EURGBP=X": (0.8, "GBP"),
    "EURHUF=X": (400.0, "HUF"),
    "IE00TEST0001": (12.0, "EUR"),
    "USD.TEST": (10.0, "USD"),
}


class FakeTicker:
    """Minimal stand-in for ``yfinance.Ticker`` backed by ``FAKE_MARKET``."""

    def __init__(self, ticker_symbol: str):
        self.ticker = ticker_symbol
        _, currency = FAKE_MARKET.get(ticker_symbol, (None, None))
        self.fast_info = {"currency": currency}

    def history(self, period: str) -> pd.DataFrame:
        if self.ticker not in FAKE_MARKET:
            return pd.DataFrame(columns=["Close"])
        price, _ = FAKE_MARKET[self.ticker]
        return pd.DataFrame(
            {"Close": [price * 0.9, price]},
            index=pd.to_datetime(["2026-10-14", "2026-10-15"]),
        )


@pytest.fixture
def fake_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace yfinance with ``FakeTicker`` and reset the price caches."""
    monkeypatch.setattr(market_data.yf, "Ticker", FakeTicker)
    market_data.get_eur_per_unit.cache_clear()
    market_data.get_latest_quote.cache_clear()
    yield
    market_data.get_eur_per_unit.cache_clear()
    market_data.get_latest_quote.cache_clear()
