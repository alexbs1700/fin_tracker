"""Tests for fin_tracker.categorization.pipeline."""

from fin_tracker.categorization.overrides import save_override
from fin_tracker.categorization.pipeline import categorize_transactions
from tests.conftest import TEST_OWNER_NAME, build_transactions


def test_categorize_transactions_runs_rules_pairing_and_overrides(tmp_path):
    path_rules = tmp_path / "rules.yaml"
    path_rules.write_text(
        "rules:\n"
        "  - name: own_transfer\n"
        "    match: {text: '{owner_name}'}\n"
        "    flow_type: internal_transfer\n"
        "    category: Traspaso interno\n"
        "    pair_transfer: true\n",
        encoding="utf-8",
    )
    path_overrides = tmp_path / "overrides.csv"
    save_override("key-2", "Ocio", path_overrides=path_overrides)

    df_transactions = build_transactions(
        [
            {"date": "2026-01-01", "account": "bbva", "amount": -100.0, "description": TEST_OWNER_NAME},
            {"date": "2026-01-01", "account": "revolut", "amount": 100.0, "description": TEST_OWNER_NAME},
            {"date": "2026-01-02", "account": "revolut", "amount": -5.0, "description": "Cinema"},
        ]
    )  # fmt: skip
    df_categorized = categorize_transactions(
        df_transactions,
        path_rules=path_rules,
        path_overrides=path_overrides,
        dict_placeholders={"owner_name": TEST_OWNER_NAME},
    )

    assert df_categorized["flow_type"].astype(str).tolist() == [
        "internal_transfer",
        "internal_transfer",
        "expense",
    ]
    assert df_categorized["transfer_id"].tolist()[:2] == ["T00001", "T00001"]
    assert df_categorized["category"].iloc[2] == "Ocio"
    assert df_categorized["is_category_override"].tolist() == [False, False, True]
