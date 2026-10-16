"""Tests for fin_tracker.ingestion.trade_republic."""

import pandas as pd

from fin_tracker.config import FILE_NAME_TRADE_REPUBLIC
from fin_tracker.ingestion.trade_republic import (
    load_trade_republic,
    normalize_trade_republic,
    read_trade_republic_raw,
)
from tests.conftest import TR_ROWS


def test_read_trade_republic_raw_reads_every_row(path_raw_data):
    df_tr_raw = read_trade_republic_raw(path_raw_data / FILE_NAME_TRADE_REPUBLIC)
    assert len(df_tr_raw) == len(TR_ROWS)


def test_normalize_trade_republic_splits_assets_from_counterparties(path_raw_data):
    df_tr = normalize_trade_republic(
        read_trade_republic_raw(path_raw_data / FILE_NAME_TRADE_REPUBLIC)
    )
    row_buy = df_tr[df_tr["transaction_type"] == "BUY"].iloc[0]
    row_card = df_tr[df_tr["transaction_type"] == "CARD_TRANSACTION"].iloc[0]

    assert row_buy["asset_name"] == "Test ETF"
    assert pd.isna(row_buy["counterparty_name"])
    assert row_buy["sub_account"] == "trading"
    assert row_buy["fee"] == -1.0

    assert row_card["counterparty_name"] == "SHOP"
    assert pd.isna(row_card["asset_name"])
    assert row_card["mcc_code"] == 5411

    assert str(df_tr["timestamp"].dt.tz) == "UTC"
    assert (df_tr["amount_eur"] == df_tr["amount"]).all()


def test_load_trade_republic_equals_read_then_normalize(path_raw_data):
    path_file = path_raw_data / FILE_NAME_TRADE_REPUBLIC
    pd.testing.assert_frame_equal(
        load_trade_republic(path_file),
        normalize_trade_republic(read_trade_republic_raw(path_file)),
    )
