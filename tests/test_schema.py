"""Tests for fin_tracker.schema."""

import pandas as pd

from fin_tracker.schema import UNIFIED_SCHEMA, compute_net_cash_eur, conform_to_schema


def test_conform_to_schema_adds_missing_columns_in_order():
    df_conformed = conform_to_schema(
        pd.DataFrame({"amount": [1.0], "account": ["bbva"]})
    )
    assert df_conformed.columns.tolist() == list(UNIFIED_SCHEMA)
    assert df_conformed["sub_account"].isna().all()


def test_conform_to_schema_drops_unknown_columns_and_casts_types():
    df_conformed = conform_to_schema(
        pd.DataFrame({"account": ["revolut"], "mcc_code": [5411.0], "extra": [1]})
    )
    assert "extra" not in df_conformed.columns
    assert str(df_conformed["mcc_code"].dtype) == "Int64"
    assert isinstance(df_conformed["account"].dtype, pd.CategoricalDtype)


def test_compute_net_cash_eur_adds_fees_and_taxes():
    df_transactions = conform_to_schema(
        pd.DataFrame(
            {
                "amount_eur": [-100.0, 2.0],
                "fee_eur": [-1.0, None],
                "tax_eur": [None, -0.5],
            }
        )
    )
    assert compute_net_cash_eur(df_transactions).tolist() == [-101.0, 1.5]
