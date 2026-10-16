"""Match the two legs of every transfer between my own accounts.

Each leg flagged with ``pair_transfer`` is matched to a leg of the opposite
sign in a different (account, sub_account), with the same EUR amount and a
close date. Matched legs share a ``transfer_id`` so every euro that moves
between accounts can be traced. Legs without a counterpart keep an empty
``transfer_id`` and should be reviewed (the other side may be outside the
extracts, e.g. an older period or an untracked account).
"""

import pandas as pd

from fin_tracker.config import (
    TRANSFER_AMOUNT_TOLERANCE_EUR,
    TRANSFER_FX_AMOUNT_TOLERANCE,
    TRANSFER_FX_MIN_TOLERANCE_EUR,
    TRANSFER_MATCH_WINDOW_DAYS,
)


def is_amount_match(
    amount_out_eur: float,
    amount_in_eur: float,
    is_same_currency: bool,
) -> bool:
    """Check whether an outflow and an inflow can be the same transfer.

    FX conversions are compared with a relative tolerance (with a small absolute
    floor for cent-sized round-ups) because each wallet reports its EUR
    equivalent at a slightly different rate.

    Args:
        amount_out_eur: Negative EUR amount of the outgoing leg.
        amount_in_eur: Positive EUR amount of the incoming leg.
        is_same_currency: Whether both legs are in the same currency.

    Returns:
        True if the amounts are compatible.
    """
    difference_eur = abs(amount_out_eur + amount_in_eur)
    if is_same_currency:
        return difference_eur <= TRANSFER_AMOUNT_TOLERANCE_EUR
    return difference_eur <= max(
        TRANSFER_FX_AMOUNT_TOLERANCE * abs(amount_out_eur),
        TRANSFER_FX_MIN_TOLERANCE_EUR,
    )


def pair_transfers(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Assign a shared ``transfer_id`` to matching transfer legs.

    Outflows are processed oldest first. Each one takes the unmatched inflow
    with the closest date (ties broken by the closest amount), restricted to
    the rule's ``counterpart_account`` when either leg sets one. BBVA's value
    date is used when present because card top-ups book days later.

    Args:
        df_transactions: Categorized transactions with a ``pair_transfer`` column.

    Returns:
        Copy of the input with ``transfer_id`` and ``transfer_counterparty_key``.
    """
    df_paired = df_transactions.copy()
    df_paired["transfer_id"] = pd.Series(pd.NA, index=df_paired.index, dtype="string")
    df_paired["transfer_counterparty_key"] = pd.Series(
        pd.NA, index=df_paired.index, dtype="string"
    )

    df_legs = df_paired[df_paired["pair_transfer"]].assign(
        effective_date=lambda df: df["value_date"].fillna(df["date"]),
        wallet=lambda df: (
            df["account"].astype("string") + "/" + df["sub_account"].fillna("")
        ),
    )
    df_outflows = df_legs[df_legs["amount_eur"] < 0].sort_values("effective_date")
    df_inflows = df_legs[df_legs["amount_eur"] > 0]
    set_used_inflow_indices: set = set()
    transfer_number = 0

    for index_outflow, outflow in df_outflows.iterrows():
        series_days_apart = (
            df_inflows["effective_date"] - outflow["effective_date"]
        ).abs()
        df_candidates = df_inflows[
            (series_days_apart <= pd.Timedelta(days=TRANSFER_MATCH_WINDOW_DAYS))
            & (df_inflows["wallet"] != outflow["wallet"])
            & ~df_inflows.index.isin(set_used_inflow_indices)
        ]
        # Respect the expected destination of the outflow and origin of the inflow
        if pd.notna(outflow["counterpart_account"]):
            df_candidates = df_candidates[
                df_candidates["account"] == outflow["counterpart_account"]
            ]
        df_candidates = df_candidates[
            df_candidates["counterpart_account"].isna()
            | (df_candidates["counterpart_account"] == outflow["account"])
        ]
        is_compatible = [
            is_amount_match(
                outflow["amount_eur"],
                inflow["amount_eur"],
                inflow["currency"] == outflow["currency"],
            )
            for _, inflow in df_candidates.iterrows()
        ]
        df_candidates = df_candidates[is_compatible]
        if df_candidates.empty:
            continue

        index_inflow = (
            df_candidates.assign(
                days_apart=series_days_apart.loc[df_candidates.index],
                amount_gap=(df_candidates["amount_eur"] + outflow["amount_eur"]).abs(),
            )
            .sort_values(["days_apart", "amount_gap"], kind="stable")
            .index[0]
        )
        set_used_inflow_indices.add(index_inflow)
        transfer_number += 1
        transfer_id = f"T{transfer_number:05d}"

        df_paired.loc[[index_outflow, index_inflow], "transfer_id"] = transfer_id
        df_paired.loc[index_outflow, "transfer_counterparty_key"] = df_paired.loc[
            index_inflow, "transaction_key"
        ]
        df_paired.loc[index_inflow, "transfer_counterparty_key"] = df_paired.loc[
            index_outflow, "transaction_key"
        ]

    return df_paired
