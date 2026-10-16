"""Tests for fin_tracker.categorization.rules."""

import pandas as pd
import pytest

from fin_tracker.categorization.rules import (
    DEFAULT_EXPENSE_CATEGORY,
    DEFAULT_INCOME_CATEGORY,
    FALLBACK_RULE_NAME,
    Rule,
    apply_rules,
    build_search_text,
    fill_placeholders,
    load_rules,
    match_rule,
    normalize_string,
    normalize_text,
    parse_rule,
)
from fin_tracker.config import PATH_CATEGORY_RULES
from tests.conftest import TEST_OWNER_NAME, build_transactions

DICT_PLACEHOLDERS = {"owner_name": TEST_OWNER_NAME}


def test_normalize_string_strips_accents_case_and_spaces():
    assert normalize_string("  Abono de  NÓMINA ") == "abono de nomina"


def test_normalize_text_handles_missing_values():
    assert normalize_text(pd.Series(["Café", None])).tolist() == ["cafe", ""]


def test_build_search_text_joins_text_columns():
    df_transactions = build_transactions(
        [{"date": "2026-01-01", "amount": -1.0, "description": "Shop", "details": "X"}]
    )
    assert build_search_text(df_transactions).iloc[0] == "shop |  | x | "


def test_fill_placeholders_escapes_and_normalizes():
    pattern = fill_placeholders(
        "^pago de {owner_name}$", {"owner_name": "Ana Pérez (2)"}
    )
    assert pattern == r"^pago de ana\ perez\ \(2\)$"


def test_fill_placeholders_raises_on_empty_value():
    with pytest.raises(ValueError, match="owner_name"):
        fill_placeholders("{owner_name}", {"owner_name": ""})


def test_fill_placeholders_ignores_unused_empty_values():
    assert fill_placeholders("mercadona", {"owner_name": ""}) == "mercadona"


def test_parse_rule_reads_every_matcher():
    rule = parse_rule(
        {
            "name": "r",
            "flow_type": "internal_transfer",
            "category": "C",
            "pair_transfer": True,
            "counterpart_account": "revolut",
            "match": {
                "account": ["bbva"],
                "text": "{owner_name}",
                "fields": {"description": "^x"},
                "sign": "negative",
            },
        },
        DICT_PLACEHOLDERS,
    )
    assert rule.dict_exact_matches == {"account": ["bbva"]}
    assert rule.text_pattern == r"test\ owner"
    assert rule.dict_field_patterns == {"description": "^x"}
    assert rule.sign == "negative"
    assert rule.pair_transfer
    assert rule.counterpart_account == "revolut"


def test_parse_rule_rejects_unknown_flow_type():
    with pytest.raises(ValueError, match="unknown flow_type"):
        parse_rule({"name": "r", "flow_type": "gift", "category": "C"}, {})


def test_load_rules_keeps_file_order(tmp_path):
    path_rules = tmp_path / "rules.yaml"
    path_rules.write_text(
        "rules:\n"
        "  - {name: first, flow_type: expense, category: A}\n"
        "  - {name: second, flow_type: income, category: B}\n",
        encoding="utf-8",
    )
    assert [rule.name for rule in load_rules(path_rules, DICT_PLACEHOLDERS)] == [
        "first",
        "second",
    ]


@pytest.fixture
def df_transactions():
    return build_transactions(
        [
            {"date": "2026-01-01", "account": "bbva", "amount": -10.0,
             "description": "Mercadona", "transaction_type": "Pago con tarjeta"},
            {"date": "2026-01-02", "account": "revolut", "amount": 5.0,
             "description": "Mercadona refund", "bank_category": "Reembolso"},
            {"date": "2026-01-03", "account": "bbva", "amount": -20.0,
             "description": "Transferencia realizada", "transaction_type": "Obaabc1234567890"},
        ]
    )  # fmt: skip


@pytest.mark.parametrize(
    ("rule", "expected_mask"),
    [
        (Rule("r", "expense", "C", dict_exact_matches={"account": ["bbva"]}), [True, False, True]),
        (Rule("r", "expense", "C", dict_exact_matches={"bank_category": ["Reembolso"]}), [False, True, False]),
        (Rule("r", "expense", "C", text_pattern="mercadona"), [True, True, False]),
        (Rule("r", "expense", "C", dict_field_patterns={"transaction_type": "^oba"}), [False, False, True]),
        (Rule("r", "expense", "C", text_pattern="mercadona", sign="negative"), [True, False, False]),
        (Rule("r", "expense", "C", sign="positive"), [False, True, False]),
    ],
)  # fmt: skip
def test_match_rule(df_transactions, rule, expected_mask):
    series_search_text = build_search_text(df_transactions)
    assert (
        match_rule(rule, df_transactions, series_search_text).tolist() == expected_mask
    )


def test_apply_rules_first_match_wins_and_falls_back(df_transactions):
    list_rules = [
        Rule("supermarket", "expense", "Supermercado", text_pattern="mercadona", sign="negative"),
        Rule("catch_all_mercadona", "expense", "Otro", text_pattern="mercadona"),
        Rule("open_banking", "internal_transfer", "Traspaso interno",
             pair_transfer=True, counterpart_account="revolut",
             dict_field_patterns={"transaction_type": "^oba"}),
    ]  # fmt: skip
    df_categorized = apply_rules(df_transactions, list_rules)

    assert df_categorized["category"].tolist() == [
        "Supermercado",
        "Otro",
        "Traspaso interno",
    ]
    assert df_categorized["category_rule"].tolist() == [
        "supermarket",
        "catch_all_mercadona",
        "open_banking",
    ]
    assert df_categorized["pair_transfer"].tolist() == [False, False, True]
    assert df_categorized["counterpart_account"].iloc[2] == "revolut"


def test_apply_rules_fallback_uses_sign(df_transactions):
    df_categorized = apply_rules(df_transactions, [])
    assert df_categorized["flow_type"].astype(str).tolist() == [
        "expense",
        "income",
        "expense",
    ]
    assert df_categorized["category"].tolist() == [
        DEFAULT_EXPENSE_CATEGORY,
        DEFAULT_INCOME_CATEGORY,
        DEFAULT_EXPENSE_CATEGORY,
    ]
    assert (df_categorized["category_rule"] == FALLBACK_RULE_NAME).all()


def test_project_rules_classify_key_movements():
    """Regression test of config/categories.yaml on the movements that matter most."""
    owner = TEST_OWNER_NAME.upper()
    df_transactions = build_transactions(
        [
            {"date": "2026-01-01", "account": "bbva", "amount": -500.0, "description": "Transferencia realizada", "transaction_type": "La pasta del mes"},
            {"date": "2026-01-02", "account": "revolut", "sub_account": "Cuenta personal (EUR)", "amount": 500.0, "description": f"Pago de {owner}"},
            {"date": "2026-01-03", "account": "revolut", "sub_account": "Cuenta personal (EUR)", "amount": -50.0, "description": f"Transferencia a {owner} & PARTNER"},
            {"date": "2026-01-03", "account": "revolut", "sub_account": "Cuenta Conjunta (EUR)", "amount": 50.0, "description": f"Transferencia de {owner}"},
            {"date": "2026-01-04", "account": "revolut", "sub_account": "Cuenta Conjunta (EUR)", "amount": -30.0, "description": "Restaurante"},
            {"date": "2026-01-05", "account": "trade_republic", "amount": -100.0, "transaction_type": "BUY", "description": "Buy trade"},
            {"date": "2026-01-06", "account": "bbva", "amount": -24.0, "description": "Mercadona c. ma", "transaction_type": "Pago con tarjeta"},
            {"date": "2026-01-07", "account": "bbva", "amount": 2000.0, "description": "Abono de nómina", "transaction_type": "Empresa SL"},
            {"date": "2026-01-08", "account": "trade_republic", "amount": -100.0, "transaction_type": "CARD_TRANSACTION", "description": "Revolut**1234*"},
        ]
    )  # fmt: skip
    df_categorized = apply_rules(
        df_transactions, load_rules(PATH_CATEGORY_RULES, DICT_PLACEHOLDERS)
    )
    assert df_categorized["flow_type"].astype(str).tolist() == [
        "internal_transfer",
        "internal_transfer",
        "expense",
        "excluded",
        "excluded",
        "investment",
        "expense",
        "income",
        "internal_transfer",
    ]
    assert df_categorized["category"].iloc[2] == "Cuenta conjunta"
    assert df_categorized["category"].iloc[6] == "Supermercado"
    assert df_categorized["category"].iloc[7] == "Nómina"
