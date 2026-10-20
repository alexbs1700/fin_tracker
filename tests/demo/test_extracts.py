"""Tests for fin_tracker.demo.extracts."""

import pandas as pd
import pytest

from fin_tracker.config import (
    FILE_NAME_BBVA,
    FILE_NAME_REVOLUT,
    FILE_NAME_TRADE_REPUBLIC,
)
from fin_tracker.demo.extracts import (
    DEMO_MONTHS,
    HUF_WALLET,
    OPENING_BALANCE_BBVA_EUR,
    PERSONAL_WALLET,
    ROUND_UP_WALLET,
    DemoLedger,
    add_budapest_trip,
    add_opening_movements,
    add_savings_plan,
    build_demo_ledger,
    build_revolut_wallet_lines,
    compute_salary_by_month,
    draw_amount,
    format_spanish_date,
    format_spanish_money,
    get_day,
    get_demo_months,
    get_last_business_day,
    with_running_balance,
    write_demo_extracts,
)
from fin_tracker.demo.market import get_price_on
from fin_tracker.ingestion.banks import BANKS
from fin_tracker.ingestion.validation import validate_extract
from tests.demo.conftest import DEMO_END_DATE


@pytest.fixture(scope="module")
def ledger() -> DemoLedger:
    return build_demo_ledger(DEMO_END_DATE)


def test_get_demo_months_ends_with_the_current_month():
    list_months = get_demo_months(DEMO_END_DATE)
    assert len(list_months) == DEMO_MONTHS
    assert list_months[-1] == pd.Period("2026-10", freq="M")


def test_compute_salary_by_month_pays_extras_and_a_june_refund():
    df_salary = compute_salary_by_month(get_demo_months(DEMO_END_DATE))
    assert (
        df_salary.loc["2025-12", "salary_net_eur"]
        > 1.8 * df_salary.loc["2025-11", "salary_net_eur"]
    )
    assert df_salary.loc["2026-06", "tax_refund_eur"] != 0
    assert df_salary.loc["2026-05", "tax_refund_eur"] == 0


def test_get_day_clips_to_the_month_length():
    assert get_day(pd.Period("2026-02", freq="M"), 31) == pd.Timestamp("2026-02-28")


def test_get_last_business_day_skips_weekends():
    # 2026-05-31 is a Sunday
    assert get_last_business_day(pd.Period("2026-05", freq="M")) == pd.Timestamp(
        "2026-05-29"
    )


def test_draw_amount_stays_within_bounds():
    import numpy as np

    rng = np.random.default_rng(0)
    assert all(5.0 <= draw_amount(rng, 5.0, 6.0) <= 6.0 for _ in range(50))


def test_add_savings_plan_buys_each_fund_at_its_close():
    ledger = DemoLedger()
    date = pd.Timestamp("2025-06-03")
    add_savings_plan(ledger, date, 1000.0)
    assert sum(row["amount"] for row in ledger.list_trade_republic) == pytest.approx(
        -1000.0
    )
    row_equity = ledger.list_trade_republic[0]
    assert row_equity["price"] == get_price_on(row_equity["symbol"], date)
    assert row_equity["shares"] * row_equity["price"] == pytest.approx(
        -row_equity["amount"], abs=0.01
    )


def test_add_opening_movements_moves_savings_with_both_legs():
    ledger = DemoLedger()
    add_opening_movements(ledger, pd.Timestamp("2025-03-01"))
    assert ledger.list_bbva[0]["amount"] == -ledger.list_trade_republic[0]["amount"]
    assert ledger.list_trade_republic[1]["type"] == "BUY"


def test_add_budapest_trip_converts_eur_and_spends_huf():
    import numpy as np

    ledger = DemoLedger()
    add_budapest_trip(ledger, pd.Period("2025-08", freq="M"), np.random.default_rng(0))
    list_huf = ledger.dict_revolut[HUF_WALLET]
    assert list_huf[0]["amount"] == 100000.0
    assert list_huf[0]["amount_eur"] == 250.0
    assert sum(row["amount"] for row in list_huf) >= 0


def test_build_demo_ledger_drops_movements_after_the_end_date(ledger):
    list_dates = [row["date"] for row in ledger.list_bbva] + [
        row["date"] for list_rows in ledger.dict_revolut.values() for row in list_rows
    ]
    assert max(list_dates) <= DEMO_END_DATE
    assert (
        max(row["date"] for row in ledger.list_trade_republic)
        <= f"{DEMO_END_DATE:%Y-%m-%d}"
    )


def test_build_demo_ledger_never_overdraws_an_account(ledger):
    assert (
        min(
            row["balance_amount"]
            for row in with_running_balance(ledger.list_bbva, OPENING_BALANCE_BBVA_EUR)
        )
        > 0
    )
    for wallet in [PERSONAL_WALLET, HUF_WALLET, ROUND_UP_WALLET]:
        opening = 600.0 if wallet == PERSONAL_WALLET else 0.0
        assert (
            min(
                row["balance_amount"]
                for row in with_running_balance(ledger.dict_revolut[wallet], opening)
            )
            >= 0
        )


def test_build_demo_ledger_is_deterministic():
    assert (
        build_demo_ledger(DEMO_END_DATE).list_bbva
        == build_demo_ledger(DEMO_END_DATE).list_bbva
    )


def test_with_running_balance_sorts_and_accumulates():
    list_rows = [
        {"date": pd.Timestamp("2026-01-02"), "amount": -5.0},
        {"date": pd.Timestamp("2026-01-01"), "amount": 10.0},
    ]
    assert [
        row["balance_amount"] for row in with_running_balance(list_rows, 100.0)
    ] == [110.0, 105.0]


def test_format_spanish_money():
    assert format_spanish_money(-1234.5, "EUR") == "-1.234,50€"
    assert format_spanish_money(4000, "HUF") == "4.000,00 HUF"


def test_format_spanish_date_uses_revolut_abbreviations():
    assert format_spanish_date(pd.Timestamp("2025-09-07")) == "7 sept 2025"


def test_build_revolut_wallet_lines_without_movements_has_no_table():
    assert build_revolut_wallet_lines(ROUND_UP_WALLET, [], 0.0)[-1].startswith("---")


@pytest.mark.parametrize("bank_key", list(BANKS))
def test_write_demo_extracts_passes_upload_validation(tmp_path, bank_key):
    write_demo_extracts(tmp_path, DEMO_END_DATE)
    bank = BANKS[bank_key]
    report = validate_extract(bank, tmp_path / bank.file_name, tmp_path / "missing")
    assert report.is_valid, report.errors


def test_write_demo_extracts_writes_every_bank_file(tmp_path):
    write_demo_extracts(tmp_path / "raw", DEMO_END_DATE)
    for file_name in [FILE_NAME_BBVA, FILE_NAME_REVOLUT, FILE_NAME_TRADE_REPUBLIC]:
        assert (tmp_path / "raw" / file_name).exists()
