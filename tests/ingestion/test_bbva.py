"""Tests for fin_tracker.ingestion.bbva."""

import pandas as pd

from fin_tracker.config import FILE_NAME_BBVA
from fin_tracker.ingestion.bbva import load_bbva, normalize_bbva, read_bbva_raw


def test_read_bbva_raw_skips_title_rows_and_empty_first_column(path_raw_data):
    df_bbva_raw = read_bbva_raw(path_raw_data / FILE_NAME_BBVA)
    assert df_bbva_raw.columns[0] == "F.Valor"
    assert len(df_bbva_raw) == 2


def test_normalize_bbva_orders_oldest_first_and_cleans_text(path_raw_data):
    df_bbva = normalize_bbva(read_bbva_raw(path_raw_data / FILE_NAME_BBVA))

    assert df_bbva["date"].tolist() == [
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-02-02"),
    ]
    assert df_bbva["balance"].iloc[-1] == 980.0
    assert df_bbva["description"].iloc[-1] == "Super market"
    assert df_bbva["details"].iloc[-1] == "1111 SUPER MARKET MADRID"
    assert df_bbva["value_date"].iloc[-1] == pd.Timestamp("2026-02-01")
    assert (df_bbva["amount_eur"] == df_bbva["amount"]).all()


def test_load_bbva_equals_read_then_normalize(path_raw_data):
    path_file = path_raw_data / FILE_NAME_BBVA
    pd.testing.assert_frame_equal(
        load_bbva(path_file), normalize_bbva(read_bbva_raw(path_file))
    )
