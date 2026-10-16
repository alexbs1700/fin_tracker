"""Open positions and realized gains from the trade history, using FIFO.

FIFO is the cost method required by Spanish tax law for homogeneous securities.
Fees and transaction taxes are part of the cost of a buy and reduce the
proceeds of a sell.
"""

from collections import deque
from dataclasses import dataclass

import pandas as pd

# Positions below this many shares are rounding leftovers and treated as closed
SHARES_TOLERANCE = 1e-6
TRADE_TYPES = ["BUY", "SELL"]


@dataclass
class Lot:
    """Shares bought in a single trade that have not been sold yet."""

    shares: float
    cost_per_share_eur: float
    purchase_date: pd.Timestamp


def get_trades(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Select buy and sell trades, oldest first.

    Args:
        df_transactions: Unified transactions dataframe.

    Returns:
        Trades with a ``net_cash_eur`` column: cash flow including fees and taxes.
    """
    df_trades = df_transactions[
        df_transactions["transaction_type"].isin(TRADE_TYPES)
    ].sort_values("timestamp", kind="stable")
    return df_trades.assign(
        net_cash_eur=df_trades["amount_eur"]
        + df_trades["fee_eur"].fillna(0)
        + df_trades["tax_eur"].fillna(0)
    )


def compute_fifo_positions(
    df_transactions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute open positions and realized gains by replaying trades with FIFO.

    Args:
        df_transactions: Unified transactions dataframe.

    Returns:
        A tuple ``(df_positions, df_realized_gains)``:

        - ``df_positions``: one row per open ISIN with shares, FIFO cost basis
          and average cost per share.
        - ``df_realized_gains``: one row per sell with proceeds, FIFO cost and gain.
    """
    df_trades = get_trades(df_transactions)
    list_rows_positions = []
    list_rows_realized = []

    for asset_isin, df_asset_trades in df_trades.groupby("asset_isin", sort=False):
        deque_lots: deque[Lot] = deque()

        for trade in df_asset_trades.itertuples():
            if trade.transaction_type == "BUY":
                deque_lots.append(
                    Lot(
                        shares=trade.shares,
                        cost_per_share_eur=-trade.net_cash_eur / trade.shares,
                        purchase_date=trade.date,
                    )
                )
                continue

            # SELL: consume the oldest lots first
            shares_to_sell = -trade.shares
            cost_of_sold_shares_eur = 0.0
            while shares_to_sell > SHARES_TOLERANCE and deque_lots:
                oldest_lot = deque_lots[0]
                shares_from_lot = min(shares_to_sell, oldest_lot.shares)
                cost_of_sold_shares_eur += (
                    shares_from_lot * oldest_lot.cost_per_share_eur
                )
                oldest_lot.shares -= shares_from_lot
                shares_to_sell -= shares_from_lot
                if oldest_lot.shares <= SHARES_TOLERANCE:
                    deque_lots.popleft()

            list_rows_realized.append(
                {
                    "date": trade.date,
                    "asset_isin": asset_isin,
                    "asset_name": trade.asset_name,
                    "shares_sold": -trade.shares,
                    "proceeds_eur": trade.net_cash_eur,
                    "cost_basis_eur": cost_of_sold_shares_eur,
                    "realized_gain_eur": trade.net_cash_eur - cost_of_sold_shares_eur,
                }
            )

        shares_held = sum(lot.shares for lot in deque_lots)
        if shares_held <= SHARES_TOLERANCE:
            continue
        cost_basis_eur = sum(lot.shares * lot.cost_per_share_eur for lot in deque_lots)
        last_trade = df_asset_trades.iloc[-1]
        list_rows_positions.append(
            {
                "asset_isin": asset_isin,
                "asset_name": last_trade["asset_name"],
                "asset_class": last_trade["asset_class"],
                "shares": shares_held,
                "cost_basis_eur": cost_basis_eur,
                "average_cost_eur": cost_basis_eur / shares_held,
                "last_trade_price_eur": last_trade["price"],
            }
        )

    return pd.DataFrame(list_rows_positions), pd.DataFrame(list_rows_realized)
