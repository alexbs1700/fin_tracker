"""Tests for fin_tracker.schema."""

import pandas as pd

from fin_tracker.schema import UNIFIED_SCHEMA, conform_to_schema


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
