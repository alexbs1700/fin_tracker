"""Tests for fin_tracker.ingestion.revolut."""

import pandas as pd
import pytest

from fin_tracker.config import FILE_NAME_REVOLUT
from fin_tracker.ingestion.revolut import (
    WALLET_TABLE_MARKER,
    get_first_cell,
    load_revolut,
    normalize_revolut,
    parse_money,
    parse_spanish_date,
    read_revolut_raw,
    read_wallet_table,
    rename_revolut_column,
)
from tests.conftest import REVOLUT_LINES


def find_marker_index(wallet_name: str) -> int:
    """Return the line index of the table marker that follows ``wallet_name``."""
    index_wallet = max(
        index_line
        for index_line, line in enumerate(REVOLUT_LINES)
        if get_first_cell(line) == wallet_name
    )
    return REVOLUT_LINES.index(f'"{WALLET_TABLE_MARKER}",,,,,,,,', index_wallet)


@pytest.mark.parametrize(
    ("line", "expected_first_cell"),
    [
        ('"Cuenta personal (EUR)",,,', "Cuenta personal (EUR)"),
        (",,,", ""),
        ("", ""),
        ('"  Total ",1,2', "Total"),
    ],
)
def test_get_first_cell(line, expected_first_cell):
    assert get_first_cell(line) == expected_first_cell


def test_parse_money_handles_spanish_format_and_unicode_minus():
    series_money = pd.Series(["1.144,34€", "\u22128,99€", "0,00 HUF", "-1.000,00₹"])
    assert parse_money(series_money).tolist() == [1144.34, -8.99, 0.0, -1000.0]


def test_parse_money_returns_nan_for_garbage():
    assert parse_money(pd.Series(["n/a"])).isna().all()


def test_parse_spanish_date_handles_four_letter_september_and_case():
    series_date = pd.Series(["8 jul 2025", "7 sept 2025", "15 Dic 2026"])
    assert parse_spanish_date(series_date).dt.strftime("%Y-%m-%d").tolist() == [
        "2025-07-08",
        "2025-09-07",
        "2026-12-15",
    ]


def test_rename_revolut_column_maps_duplicates_to_eur():
    assert rename_revolut_column("Saldo") == "balance"
    assert rename_revolut_column("Saldo.1") == "balance_eur"
    assert rename_revolut_column("Unknown") == "Unknown"


def test_read_wallet_table_eur_wallet_copies_money_to_eur_columns():
    df_wallet = read_wallet_table(
        REVOLUT_LINES, find_marker_index("Cuenta personal (EUR)")
    )
    assert df_wallet["wallet"].unique().tolist() == ["Cuenta personal (EUR)"]
    assert df_wallet["amount"].tolist() == [100.0, -8.99]
    assert df_wallet["amount_eur"].tolist() == [100.0, -8.99]
    assert df_wallet["fees"].tolist() == [0.0, 8.99]


def test_read_wallet_table_fx_wallet_keeps_both_currencies():
    df_wallet = read_wallet_table(
        REVOLUT_LINES, find_marker_index("Cuenta personal (HUF)")
    )
    assert df_wallet["amount"].tolist() == [4000.0]
    assert df_wallet["amount_eur"].tolist() == [10.0]


def test_read_wallet_table_returns_empty_for_wallet_without_movements():
    assert read_wallet_table(REVOLUT_LINES, find_marker_index("Round-Up (EUR)")).empty


def test_read_revolut_raw_reads_every_non_empty_wallet(path_raw_data):
    df_revolut_raw = read_revolut_raw(path_raw_data / FILE_NAME_REVOLUT)
    assert df_revolut_raw["wallet"].unique().tolist() == [
        "Cuenta personal (EUR)",
        "Cuenta personal (HUF)",
        "Cuenta Conjunta (EUR)",
    ]
    assert df_revolut_raw["currency"].unique().tolist() == ["EUR", "HUF"]


def test_normalize_revolut_flips_fee_sign_and_keeps_amount(path_raw_data):
    df_revolut = normalize_revolut(read_revolut_raw(path_raw_data / FILE_NAME_REVOLUT))
    row_fee = df_revolut[df_revolut["description"] == "Premium plan"].iloc[0]

    # amount already includes the fee, fee is informational and negative
    assert row_fee["amount"] == -8.99
    assert row_fee["fee"] == -8.99
    assert row_fee["tax"] == 0
    assert row_fee["date"] == pd.Timestamp("2025-09-07")
    assert (df_revolut["account"] == "revolut").all()


def test_load_revolut_equals_read_then_normalize(path_raw_data):
    path_file = path_raw_data / FILE_NAME_REVOLUT
    pd.testing.assert_frame_equal(
        load_revolut(path_file), normalize_revolut(read_revolut_raw(path_file))
    )


def test_read_revolut_raw_raises_without_wallet_tables(tmp_path):
    path_file = tmp_path / "not_revolut.csv"
    path_file.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no wallet tables"):
        read_revolut_raw(path_file)
