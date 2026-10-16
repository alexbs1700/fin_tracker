"""Tests for fin_tracker.categorization.transfers."""

import pandas as pd
import pytest

from fin_tracker.categorization.transfers import is_amount_match, pair_transfers
from tests.conftest import build_transactions


@pytest.mark.parametrize(
    ("amount_out_eur", "amount_in_eur", "is_same_currency", "expected"),
    [
        (-100.0, 100.0, True, True),
        (-100.0, 100.02, True, False),
        (-100.0, 98.0, False, True),  # FX: 2% apart is within 3%
        (-100.0, 90.0, False, False),
        (-0.02, 0.01, False, True),  # cent round-ups use the absolute floor
    ],
)
def test_is_amount_match(amount_out_eur, amount_in_eur, is_same_currency, expected):
    assert is_amount_match(amount_out_eur, amount_in_eur, is_same_currency) is expected


def make_leg(date: str, account: str, amount: float, **fields) -> dict:
    """Build a transfer leg flagged for pairing."""
    return {
        "date": date,
        "account": account,
        "amount": amount,
        "pair_transfer": True,
        "counterpart_account": pd.NA,
        **fields,
    }


def run_pairing(list_rows: list[dict]) -> pd.DataFrame:
    """Build transactions with the pairing columns and pair them."""
    df_transactions = build_transactions(list_rows)
    df_transactions["pair_transfer"] = [
        row.get("pair_transfer", False) for row in list_rows
    ]
    df_transactions["counterpart_account"] = pd.Series(
        [row.get("counterpart_account", pd.NA) for row in list_rows], dtype="string"
    )
    return pair_transfers(df_transactions)


def test_pairs_legs_across_accounts_and_links_keys():
    df_paired = run_pairing(
        [
            make_leg("2026-01-01", "bbva", -100.0),
            make_leg("2026-01-02", "revolut", 100.0),
        ]
    )
    assert df_paired["transfer_id"].tolist() == ["T00001", "T00001"]
    assert df_paired["transfer_counterparty_key"].tolist() == ["key-1", "key-0"]


def test_unflagged_rows_and_unmatched_legs_stay_empty():
    df_paired = run_pairing(
        [
            make_leg("2026-01-01", "bbva", -100.0),
            {"date": "2026-01-01", "account": "revolut", "amount": 100.0},
        ]
    )
    assert df_paired["transfer_id"].isna().all()


def test_does_not_pair_within_the_same_wallet_or_outside_the_window():
    df_paired = run_pairing(
        [
            make_leg("2026-01-01", "bbva", -100.0),
            make_leg("2026-01-01", "bbva", 100.0),
            make_leg("2026-01-10", "revolut", 100.0),
        ]
    )
    assert df_paired["transfer_id"].isna().all()


def test_counterpart_account_disambiguates_equal_amounts():
    df_paired = run_pairing(
        [
            make_leg(
                "2026-01-01", "bbva", -500.0, counterpart_account="trade_republic"
            ),
            make_leg("2026-01-01", "bbva", -500.0, counterpart_account="revolut"),
            make_leg("2026-01-01", "revolut", 500.0),
            make_leg("2026-01-02", "trade_republic", 500.0),
        ]
    )
    assert df_paired["transfer_id"].tolist() == ["T00001", "T00002", "T00002", "T00001"]


def test_each_inflow_is_used_once_and_closest_date_wins():
    df_paired = run_pairing(
        [
            make_leg("2026-01-05", "bbva", -50.0),
            make_leg("2026-01-01", "revolut", 50.0),
            make_leg("2026-01-05", "revolut", 50.0),
        ]
    )
    assert df_paired["transfer_id"].tolist() == ["T00001", pd.NA, "T00001"]


def test_value_date_is_used_for_late_booked_card_top_ups():
    df_paired = run_pairing(
        [
            make_leg(
                "2026-01-20", "bbva", -17.0, value_date=pd.Timestamp("2026-01-01")
            ),
            make_leg("2026-01-01", "revolut", 17.0),
        ]
    )
    assert df_paired["transfer_id"].notna().all()
