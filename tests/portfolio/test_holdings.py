"""Tests for fin_tracker.portfolio.holdings."""

from collections import deque

import pandas as pd
import pytest

from fin_tracker.portfolio.holdings import (
    Lot,
    compute_fifo_positions,
    compute_holdings_timeline,
    get_trades,
    replay_asset_trades,
    sell_from_lots,
)
from fin_tracker.schema import conform_to_schema


def make_trade(
    timestamp: str,
    transaction_type: str,
    shares: float,
    amount: float,
    fee: float,
    asset_isin: str = "IE00TEST0001",
) -> dict:
    """Build one Trade Republic style trade row (amount excludes the fee)."""
    return {
        "account": "trade_republic",
        "date": pd.Timestamp(timestamp[:10]),
        "timestamp": pd.Timestamp(timestamp, tz="UTC"),
        "transaction_type": transaction_type,
        "asset_isin": asset_isin,
        "asset_name": f"Name {asset_isin}",
        "asset_class": "FUND",
        "shares": shares,
        "price": abs(amount / shares),
        "amount_eur": amount,
        "fee_eur": fee,
    }


@pytest.fixture
def df_transactions():
    return conform_to_schema(
        pd.DataFrame(
            [
                # Cost per share including fee: 10.10 and 20.10
                make_trade("2026-01-01T10:00:00", "BUY", 10, -100.0, -1.0),
                make_trade("2026-02-01T10:00:00", "BUY", 10, -200.0, -1.0),
                make_trade("2026-03-01T10:00:00", "SELL", -15, 450.0, -1.0),
                # Not a trade, must be ignored
                {"account": "trade_republic", "transaction_type": "DIVIDEND",
                 "date": pd.Timestamp("2026-03-02"), "amount_eur": 5.0},
            ]
        )
    )  # fmt: skip


def test_get_trades_keeps_only_trades_with_net_cash(df_transactions):
    df_trades = get_trades(df_transactions)
    assert df_trades["transaction_type"].tolist() == ["BUY", "BUY", "SELL"]
    assert df_trades["net_cash_eur"].tolist() == [-101.0, -201.0, 449.0]


def test_get_trades_sorts_by_timestamp(df_transactions):
    df_shuffled = df_transactions.iloc[::-1]
    assert get_trades(df_shuffled)["transaction_type"].tolist() == [
        "BUY",
        "BUY",
        "SELL",
    ]


def test_sell_consumes_oldest_lots_first(df_transactions):
    df_positions, df_realized_gains = compute_fifo_positions(df_transactions)

    # 10 shares from the first lot + 5 from the second
    expected_cost_eur = 10 * 10.1 + 5 * 20.1
    assert df_realized_gains["cost_basis_eur"].iloc[0] == pytest.approx(
        expected_cost_eur
    )
    assert df_realized_gains["realized_gain_eur"].iloc[0] == pytest.approx(
        449.0 - expected_cost_eur
    )

    assert df_positions["shares"].iloc[0] == pytest.approx(5)
    assert df_positions["cost_basis_eur"].iloc[0] == pytest.approx(5 * 20.1)
    assert df_positions["average_cost_eur"].iloc[0] == pytest.approx(20.1)


def test_fully_sold_positions_are_dropped(df_transactions):
    df_closing_sell = conform_to_schema(
        pd.DataFrame([make_trade("2026-04-01T10:00:00", "SELL", -5, 150.0, -1.0)])
    )
    df_positions, df_realized_gains = compute_fifo_positions(
        pd.concat([df_transactions, df_closing_sell], ignore_index=True)
    )
    assert df_positions.empty
    assert len(df_realized_gains) == 2


def test_assets_are_tracked_independently(df_transactions):
    df_other_asset = conform_to_schema(
        pd.DataFrame(
            [make_trade("2026-01-15T10:00:00", "BUY", 2, -50.0, 0.0, "IE00OTHER001")]
        )
    )
    df_positions, _ = compute_fifo_positions(
        pd.concat([df_transactions, df_other_asset], ignore_index=True)
    )
    assert df_positions.set_index("asset_isin")["shares"].to_dict() == pytest.approx(
        {"IE00TEST0001": 5, "IE00OTHER001": 2}
    )


def test_sell_from_lots_consumes_and_removes_oldest_lots():
    deque_lots = deque(
        [
            Lot(
                shares=2,
                cost_per_share_eur=10.0,
                purchase_date=pd.Timestamp("2026-01-01"),
            ),
            Lot(
                shares=3,
                cost_per_share_eur=20.0,
                purchase_date=pd.Timestamp("2026-02-01"),
            ),
        ]
    )
    assert sell_from_lots(deque_lots, 3) == pytest.approx(2 * 10.0 + 1 * 20.0)
    assert len(deque_lots) == 1
    assert deque_lots[0].shares == pytest.approx(2)


def test_replay_asset_trades_returns_lots_realized_and_timeline(df_transactions):
    df_asset_trades = get_trades(df_transactions)
    deque_lots, list_rows_realized, list_rows_timeline = replay_asset_trades(
        df_asset_trades
    )
    assert sum(lot.shares for lot in deque_lots) == pytest.approx(5)
    assert len(list_rows_realized) == 1
    assert [row["shares"] for row in list_rows_timeline] == pytest.approx([10, 20, 5])
    assert list_rows_timeline[-1]["cost_basis_eur"] == pytest.approx(5 * 20.1)


def test_compute_holdings_timeline_keeps_last_position_per_day(df_transactions):
    df_same_day_buy = conform_to_schema(
        pd.DataFrame([make_trade("2026-03-01T15:00:00", "BUY", 1, -30.0, 0.0)])
    )
    df_timeline = compute_holdings_timeline(
        pd.concat([df_transactions, df_same_day_buy], ignore_index=True)
    )
    assert (
        df_timeline["date"].tolist()
        == pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]).tolist()
    )
    assert df_timeline["shares"].tolist() == pytest.approx([10, 20, 6])
