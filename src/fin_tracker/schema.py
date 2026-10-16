"""Unified transactions schema shared by every bank parser."""

import pandas as pd

ACCOUNTS = ["bbva", "revolut", "trade_republic"]

# Column order and dtype of the unified transactions dataframe.
# Money follows the cash flow sign: income is positive, spending, fees and taxes negative.
UNIFIED_SCHEMA = {
    # Origin
    "account": pd.CategoricalDtype(ACCOUNTS),
    "sub_account": "string",
    "transaction_id": "string",
    # Dates
    "date": "datetime64[ns]",
    "value_date": "datetime64[ns]",
    "timestamp": "datetime64[ns, UTC]",
    # Classification and descriptions
    "transaction_type": "string",
    "category": "string",
    "description": "string",
    "details": "string",
    # Counterparty
    "counterparty_name": "string",
    "counterparty_iban": "string",
    "payment_reference": "string",
    "mcc_code": "Int64",
    # Investment
    "asset_class": "string",
    "asset_name": "string",
    "asset_isin": "string",
    "shares": "Float64",
    "price": "Float64",
    # Money
    "amount": "Float64",
    "currency": "string",
    "amount_eur": "Float64",
    "fee": "Float64",
    "fee_eur": "Float64",
    "tax": "Float64",
    "tax_eur": "Float64",
    "original_amount": "Float64",
    "original_currency": "string",
    "fx_rate": "Float64",
    "balance": "Float64",
    "balance_eur": "Float64",
}


def conform_to_schema(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Add missing columns, enforce column order and cast to the unified dtypes.

    Args:
        df_transactions: Transactions with any subset of the unified columns.

    Returns:
        A dataframe with exactly the columns of ``UNIFIED_SCHEMA``.
    """
    return df_transactions.reindex(columns=list(UNIFIED_SCHEMA)).astype(UNIFIED_SCHEMA)
