"""Manual category corrections, stored per transaction and applied over the rules."""

from pathlib import Path

import pandas as pd

from fin_tracker.categorization.rules import FLOW_TYPES
from fin_tracker.config import PATH_CATEGORY_OVERRIDES

OVERRIDE_COLUMNS = ["transaction_key", "category", "flow_type", "updated_at"]


def load_overrides(path_overrides: Path = PATH_CATEGORY_OVERRIDES) -> pd.DataFrame:
    """Read the stored overrides, or an empty table if none exist yet.

    Args:
        path_overrides: CSV file with one row per corrected transaction.

    Returns:
        Overrides with ``OVERRIDE_COLUMNS``.
    """
    if not path_overrides.exists():
        return pd.DataFrame(columns=OVERRIDE_COLUMNS).astype("string")
    return pd.read_csv(path_overrides, dtype="string")


def save_override(
    transaction_key: str,
    category: str,
    flow_type: str | None = None,
    path_overrides: Path = PATH_CATEGORY_OVERRIDES,
) -> pd.DataFrame:
    """Store (or replace) the manual category of one transaction.

    Args:
        transaction_key: Key of the transaction to correct.
        category: New category label.
        flow_type: Optional new flow type, kept from the rules when omitted.
        path_overrides: CSV file with the overrides.

    Returns:
        All overrides after the change.

    Raises:
        ValueError: If ``flow_type`` is not a known flow type.
    """
    if flow_type is not None and flow_type not in FLOW_TYPES:
        raise ValueError(f"Unknown flow_type {flow_type}")

    df_overrides = load_overrides(path_overrides)
    df_overrides = df_overrides[df_overrides["transaction_key"] != transaction_key]
    df_new_override = pd.DataFrame(
        [
            {
                "transaction_key": transaction_key,
                "category": category,
                "flow_type": flow_type,
                "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            }
        ]
    ).astype("string")
    df_overrides = pd.concat([df_overrides, df_new_override], ignore_index=True)

    path_overrides.parent.mkdir(parents=True, exist_ok=True)
    df_overrides.to_csv(path_overrides, index=False)
    return df_overrides


def apply_overrides(
    df_transactions: pd.DataFrame, df_overrides: pd.DataFrame
) -> pd.DataFrame:
    """Replace rule-based categories with the manual ones.

    Args:
        df_transactions: Categorized transactions with ``transaction_key``.
        df_overrides: Output of :func:`load_overrides`.

    Returns:
        Copy of the input with overrides applied and an ``is_category_override`` flag.
    """
    df_overridden = df_transactions.copy()
    df_overrides_by_key = df_overrides.set_index("transaction_key")
    is_overridden = df_overridden["transaction_key"].isin(df_overrides_by_key.index)
    series_keys = df_overridden.loc[is_overridden, "transaction_key"]

    df_overridden.loc[is_overridden, "category"] = df_overrides_by_key.loc[
        series_keys, "category"
    ].to_numpy()
    series_override_flow_types = df_overrides_by_key.loc[series_keys, "flow_type"]
    has_flow_type = series_override_flow_types.notna().to_numpy()
    df_overridden.loc[series_keys.index[has_flow_type], "flow_type"] = (
        series_override_flow_types[has_flow_type].to_numpy()
    )
    df_overridden["is_category_override"] = is_overridden
    return df_overridden
