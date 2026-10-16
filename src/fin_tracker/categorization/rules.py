"""Rule engine that assigns a flow type and a category to every transaction.

Rules live in ``config/categories.yaml`` (see that file for the syntax).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from fin_tracker.config import OWNER_NAME, PATH_CATEGORY_RULES

FLOW_TYPES = [
    "internal_transfer",
    "investment",
    "investment_income",
    "income",
    "expense",
    "excluded",
]
DEFAULT_EXPENSE_CATEGORY = "Otros gastos"
DEFAULT_INCOME_CATEGORY = "Otros ingresos"
FALLBACK_RULE_NAME = "fallback"

# Columns joined into the free text that the ``text`` matcher searches
TEXT_COLUMNS = ["description", "transaction_type", "details", "counterparty_name"]
EXACT_MATCH_KEYS = ["account", "sub_account", "bank_category", "transaction_type"]


@dataclass(frozen=True)
class Rule:
    """A single categorization rule loaded from the YAML file."""

    name: str
    flow_type: str
    category: str
    pair_transfer: bool = False
    counterpart_account: str | None = None
    dict_exact_matches: dict[str, list[str]] = field(default_factory=dict)
    text_pattern: str | None = None
    dict_field_patterns: dict[str, str] = field(default_factory=dict)
    sign: str | None = None


def normalize_text(series_text: pd.Series) -> pd.Series:
    """Lowercase, strip accents and collapse whitespace so rules match reliably.

    Args:
        series_text: Any text series, missing values allowed.

    Returns:
        Normalized string series, empty string where the input was missing.
    """
    return (
        series_text.astype("string").fillna("").map(normalize_string).astype("string")
    )


def normalize_string(text: str) -> str:
    """Normalize a single string, see :func:`normalize_text`."""
    text_without_accents = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return " ".join(text_without_accents.lower().split())


def build_search_text(df_transactions: pd.DataFrame) -> pd.Series:
    """Join the text columns into the single string searched by ``text`` rules."""
    list_series_text = [
        normalize_text(df_transactions[column]) for column in TEXT_COLUMNS
    ]
    series_search_text = list_series_text[0]
    for series_text in list_series_text[1:]:
        series_search_text = series_search_text + " | " + series_text
    return series_search_text


def fill_placeholders(pattern: str, dict_placeholders: dict[str, str]) -> str:
    """Replace ``{placeholder}`` tokens with regex-escaped, normalized values.

    Args:
        pattern: Regex pattern from the YAML file.
        dict_placeholders: Placeholder name to raw value.

    Returns:
        The pattern with every known placeholder substituted.

    Raises:
        ValueError: If a placeholder used in the pattern has an empty value.
    """
    for placeholder_name, placeholder_value in dict_placeholders.items():
        token = "{" + placeholder_name + "}"
        if token not in pattern:
            continue
        if not placeholder_value:
            raise ValueError(f"Placeholder {token} is empty, set it in .env")
        pattern = pattern.replace(token, re.escape(normalize_string(placeholder_value)))
    return pattern


def parse_rule(dict_rule: dict, dict_placeholders: dict[str, str]) -> Rule:
    """Build a :class:`Rule` from one YAML entry.

    Args:
        dict_rule: Raw rule as loaded from YAML.
        dict_placeholders: Values for ``{placeholder}`` tokens in patterns.

    Returns:
        The parsed rule.

    Raises:
        ValueError: If the flow type is unknown.
    """
    if dict_rule["flow_type"] not in FLOW_TYPES:
        raise ValueError(f"Rule {dict_rule['name']}: unknown flow_type")
    dict_match = dict_rule.get("match", {})
    text_pattern = dict_match.get("text")
    return Rule(
        name=dict_rule["name"],
        flow_type=dict_rule["flow_type"],
        category=dict_rule["category"],
        pair_transfer=dict_rule.get("pair_transfer", False),
        counterpart_account=dict_rule.get("counterpart_account"),
        dict_exact_matches={
            key: [str(value) for value in dict_match[key]]
            for key in EXACT_MATCH_KEYS
            if key in dict_match
        },
        text_pattern=fill_placeholders(text_pattern, dict_placeholders)
        if text_pattern
        else None,
        dict_field_patterns={
            column: fill_placeholders(pattern, dict_placeholders)
            for column, pattern in dict_match.get("fields", {}).items()
        },
        sign=dict_match.get("sign"),
    )


def load_rules(
    path_rules: Path = PATH_CATEGORY_RULES,
    dict_placeholders: dict[str, str] | None = None,
) -> list[Rule]:
    """Load the ordered list of rules from YAML.

    Args:
        path_rules: Path to the rules YAML file.
        dict_placeholders: Placeholder values. Defaults to ``{"owner_name": OWNER_NAME}``.

    Returns:
        Rules in evaluation order.
    """
    dict_placeholders = dict_placeholders or {"owner_name": OWNER_NAME}
    dict_config = yaml.safe_load(path_rules.read_text(encoding="utf-8"))
    return [
        parse_rule(dict_rule, dict_placeholders) for dict_rule in dict_config["rules"]
    ]


def match_rule(
    rule: Rule, df_transactions: pd.DataFrame, series_search_text: pd.Series
) -> pd.Series:
    """Return a boolean mask of the transactions matched by ``rule``.

    Args:
        rule: Rule to evaluate.
        df_transactions: Unified transactions dataframe.
        series_search_text: Output of :func:`build_search_text` for the same rows.

    Returns:
        Boolean series aligned with ``df_transactions``.
    """
    is_match = pd.Series(True, index=df_transactions.index)
    for column, list_allowed_values in rule.dict_exact_matches.items():
        is_match &= df_transactions[column].astype("string").isin(list_allowed_values)
    if rule.text_pattern:
        is_match &= series_search_text.str.contains(rule.text_pattern, regex=True)
    for column, pattern in rule.dict_field_patterns.items():
        is_match &= normalize_text(df_transactions[column]).str.contains(
            pattern, regex=True
        )
    if rule.sign == "negative":
        is_match &= df_transactions["amount"] < 0
    elif rule.sign == "positive":
        is_match &= df_transactions["amount"] > 0
    return is_match.fillna(False).astype(bool)


def apply_rules(df_transactions: pd.DataFrame, list_rules: list[Rule]) -> pd.DataFrame:
    """Assign flow type, category and matched rule to every transaction.

    Args:
        df_transactions: Unified transactions dataframe.
        list_rules: Rules in evaluation order, first match wins.

    Returns:
        Copy of the input with ``flow_type``, ``category``, ``category_rule``,
        ``pair_transfer`` and ``counterpart_account`` columns.
    """
    df_categorized = df_transactions.copy()
    series_search_text = build_search_text(df_categorized)
    is_negative = df_categorized["amount"] < 0

    # Start from the fallback and let rules overwrite rows that are still unassigned
    df_categorized["flow_type"] = is_negative.map({True: "expense", False: "income"})
    df_categorized["category"] = is_negative.map(
        {True: DEFAULT_EXPENSE_CATEGORY, False: DEFAULT_INCOME_CATEGORY}
    )
    df_categorized["category_rule"] = FALLBACK_RULE_NAME
    df_categorized["pair_transfer"] = False
    df_categorized["counterpart_account"] = pd.NA
    is_unassigned = pd.Series(True, index=df_categorized.index)

    for rule in list_rules:
        is_newly_matched = is_unassigned & match_rule(
            rule, df_categorized, series_search_text
        )
        df_categorized.loc[is_newly_matched, "flow_type"] = rule.flow_type
        df_categorized.loc[is_newly_matched, "category"] = rule.category
        df_categorized.loc[is_newly_matched, "category_rule"] = rule.name
        df_categorized.loc[is_newly_matched, "pair_transfer"] = rule.pair_transfer
        df_categorized.loc[is_newly_matched, "counterpart_account"] = (
            rule.counterpart_account
        )
        is_unassigned &= ~is_newly_matched

    return df_categorized.astype(
        {
            "flow_type": pd.CategoricalDtype(FLOW_TYPES),
            "category": "string",
            "category_rule": "string",
            "pair_transfer": bool,
            "counterpart_account": "string",
        }
    )
