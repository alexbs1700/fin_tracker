"""End-to-end categorization: rules, transfer matching, then manual overrides."""

from pathlib import Path

import pandas as pd

from fin_tracker.categorization.overrides import apply_overrides, load_overrides
from fin_tracker.categorization.rules import apply_rules, load_rules
from fin_tracker.categorization.transfers import pair_transfers
from fin_tracker.config import PATH_CATEGORY_OVERRIDES, PATH_CATEGORY_RULES


def categorize_transactions(
    df_transactions: pd.DataFrame,
    path_rules: Path = PATH_CATEGORY_RULES,
    path_overrides: Path = PATH_CATEGORY_OVERRIDES,
    dict_placeholders: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Categorize every transaction and link internal transfer legs.

    Args:
        df_transactions: Unified transactions dataframe.
        path_rules: Rules YAML file.
        path_overrides: Manual overrides CSV file.
        dict_placeholders: Rule placeholder values, defaults to the ``.env`` ones.

    Returns:
        Transactions with ``flow_type``, ``category``, ``category_rule``,
        ``transfer_id``, ``transfer_counterparty_key`` and ``is_category_override``.
    """
    list_rules = load_rules(path_rules, dict_placeholders)
    df_categorized = pair_transfers(apply_rules(df_transactions, list_rules))
    return apply_overrides(df_categorized, load_overrides(path_overrides))
