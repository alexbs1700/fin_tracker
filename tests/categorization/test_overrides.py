"""Tests for fin_tracker.categorization.overrides."""

import pandas as pd
import pytest

from fin_tracker.categorization.overrides import (
    OVERRIDE_COLUMNS,
    apply_overrides,
    load_overrides,
    save_override,
)
from fin_tracker.categorization.rules import FLOW_TYPES
from tests.conftest import build_transactions


@pytest.fixture
def path_overrides(tmp_path):
    return tmp_path / "overrides" / "category_overrides.csv"


def test_load_overrides_returns_empty_table_without_file(path_overrides):
    df_overrides = load_overrides(path_overrides)
    assert df_overrides.empty
    assert df_overrides.columns.tolist() == OVERRIDE_COLUMNS


def test_save_override_creates_and_replaces(path_overrides):
    save_override("key-0", "Ocio", path_overrides=path_overrides)
    save_override("key-1", "Viajes", "expense", path_overrides=path_overrides)
    df_overrides = save_override("key-0", "Regalos", path_overrides=path_overrides)

    assert sorted(df_overrides["transaction_key"]) == ["key-0", "key-1"]
    df_reloaded = load_overrides(path_overrides).set_index("transaction_key")
    assert df_reloaded.loc["key-0", "category"] == "Regalos"
    assert pd.isna(df_reloaded.loc["key-0", "flow_type"])
    assert df_reloaded.loc["key-1", "flow_type"] == "expense"


def test_save_override_rejects_unknown_flow_type(path_overrides):
    with pytest.raises(ValueError, match="flow_type"):
        save_override("key-0", "Ocio", "gift", path_overrides=path_overrides)


def test_apply_overrides_replaces_category_and_optional_flow_type(path_overrides):
    df_transactions = build_transactions(
        [
            {"date": "2026-01-01", "amount": -10.0},
            {"date": "2026-01-02", "amount": -20.0},
            {"date": "2026-01-03", "amount": -30.0},
        ]
    )
    df_transactions["category"] = pd.Series(["Otros gastos"] * 3, dtype="string")
    df_transactions["flow_type"] = pd.Categorical(
        ["expense"] * 3, categories=FLOW_TYPES
    )

    save_override("key-0", "Ocio", path_overrides=path_overrides)
    save_override(
        "key-2", "Traspaso interno", "internal_transfer", path_overrides=path_overrides
    )
    df_overridden = apply_overrides(df_transactions, load_overrides(path_overrides))

    assert df_overridden["category"].tolist() == [
        "Ocio",
        "Otros gastos",
        "Traspaso interno",
    ]
    assert df_overridden["flow_type"].astype(str).tolist() == [
        "expense",
        "expense",
        "internal_transfer",
    ]
    assert df_overridden["is_category_override"].tolist() == [True, False, True]
