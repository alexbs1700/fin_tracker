"""Tests for fin_tracker.ingestion.validation."""

import pandas as pd
import pytest

from fin_tracker.ingestion.banks import BANKS
from fin_tracker.ingestion.validation import (
    ExtractReport,
    ExtractSummary,
    check_normalized,
    compare_with_current,
    count_balance_breaks,
    load_summary,
    summarize_transactions,
    validate_extract,
)
from tests.conftest import REVOLUT_LINES, build_transactions


def test_summarize_transactions():
    summary = summarize_transactions(
        build_transactions(
            [
                {"date": "2026-01-02", "amount": 1.0, "sub_account": "B"},
                {"date": "2026-01-01", "amount": 1.0, "sub_account": "A"},
            ]
        )
    )
    assert summary == ExtractSummary(
        rows=2,
        date_from=pd.Timestamp("2026-01-01"),
        date_to=pd.Timestamp("2026-01-02"),
        sub_accounts=["A", "B"],
    )


def test_count_balance_breaks_per_wallet():
    df_transactions = build_transactions(
        [
            {"date": "2026-01-01", "sub_account": "A", "amount": 10.0, "balance": 10.0},
            {"date": "2026-01-02", "sub_account": "A", "amount": -3.0, "balance": 7.0},
            {"date": "2026-01-01", "sub_account": "B", "amount": 5.0, "balance": 5.0},
            # Should be 6.0: a row is missing or misread
            {"date": "2026-01-03", "sub_account": "B", "amount": 1.0, "balance": 9.0},
        ]
    )
    assert count_balance_breaks(df_transactions) == 1


def test_check_normalized_flags_empty_and_unreadable_rows():
    list_errors, _ = check_normalized(BANKS["bbva"], build_transactions([]).iloc[0:0])
    assert list_errors == ["El extracto no contiene movimientos."]

    df_transactions = build_transactions(
        [{"date": "2026-01-01", "amount": None, "balance": 0.0}]
    )
    list_errors, _ = check_normalized(BANKS["bbva"], df_transactions)
    assert any("importe ilegible" in error for error in list_errors)


def test_check_normalized_trade_republic_rules():
    df_transactions = build_transactions(
        [
            {"date": "2026-01-01", "amount": 100.0, "transaction_id": "a", "transaction_type": "CUSTOMER_INPAYMENT"},
            {"date": "2026-01-02", "amount": -200.0, "transaction_id": "a", "transaction_type": "BUY"},
            {"date": "2026-01-03", "amount": 1.0, "transaction_id": "c", "transaction_type": "STOCK_SPLIT"},
        ]
    )  # fmt: skip
    list_errors, list_warnings = check_normalized(
        BANKS["trade_republic"], df_transactions
    )

    assert "Hay transaction_id duplicados." in list_errors
    assert any("sin ISIN" in error for error in list_errors)
    assert any("STOCK_SPLIT" in warning for warning in list_warnings)
    assert any("negativo" in warning for warning in list_warnings)


def test_compare_with_current_warns_about_lost_history():
    current = ExtractSummary(
        10, pd.Timestamp("2025-01-01"), pd.Timestamp("2026-10-01"), ["A", "B"]
    )
    new = ExtractSummary(
        5, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-09-01"), ["A"]
    )
    list_warnings = compare_with_current(new, current)

    assert len(list_warnings) == 3
    assert compare_with_current(current, current) == []


def test_load_summary(path_raw_data, tmp_path):
    bank = BANKS["revolut"]
    assert load_summary(bank, tmp_path / "missing.csv") is None
    (tmp_path / "broken.csv").write_text("nonsense", encoding="utf-8")
    assert load_summary(bank, tmp_path / "broken.csv") is None
    assert load_summary(bank, path_raw_data / bank.file_name).rows == 4


@pytest.mark.parametrize("bank_key", sorted(BANKS))
def test_validate_extract_accepts_valid_extracts(path_raw_data, bank_key):
    bank = BANKS[bank_key]
    path_file = path_raw_data / bank.file_name
    report = validate_extract(bank, path_file, path_file)

    assert report.is_valid, report.errors
    assert report.summary == report.current_summary
    assert report.warnings == []


def test_validate_extract_rejects_unreadable_and_foreign_files(path_raw_data, tmp_path):
    report = validate_extract(
        BANKS["revolut"], path_raw_data / "tr_full_data.csv", tmp_path / "none.csv"
    )
    assert not report.is_valid
    assert "No se puede leer" in report.errors[0]

    # A well-formed csv that is not a Trade Republic export
    path_other_csv = tmp_path / "other.csv"
    path_other_csv.write_text("date,amount\n2026-01-01,5\n", encoding="utf-8")
    report = validate_extract(
        BANKS["trade_republic"], path_other_csv, tmp_path / "none.csv"
    )
    assert "Faltan columnas" in report.errors[0]


def test_validate_extract_rejects_broken_running_balance(tmp_path):
    # Change the closing balance of the second EUR movement: 91.01 -> 95.00
    list_lines = [
        line.replace('"91,01€","0,00€"', '"95,00€","0,00€"') for line in REVOLUT_LINES
    ]
    path_upload = tmp_path / "upload.csv"
    path_upload.write_text("\n".join(list_lines), encoding="utf-8")

    report = validate_extract(BANKS["revolut"], path_upload, tmp_path / "none.csv")
    assert not report.is_valid
    assert "saldo no cuadra" in report.errors[0]


def test_extract_report_is_valid_without_errors():
    assert ExtractReport(bank="bbva", warnings=["x"]).is_valid
    assert not ExtractReport(bank="bbva", errors=["x"]).is_valid
