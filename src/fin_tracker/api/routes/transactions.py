"""Transaction endpoints: filtering, detail with transfer counterpart, recategorizing."""

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from fin_tracker.api.dependencies import DateFrom, DateTo, get_store, to_timestamp
from fin_tracker.api.models import (
    CategoryCatalog,
    CategoryUpdate,
    Transaction,
    TransactionPage,
)
from fin_tracker.api.serialization import dataframe_to_records, filter_date_range
from fin_tracker.api.store import FinanceDataStore
from fin_tracker.categorization.rules import (
    DEFAULT_EXPENSE_CATEGORY,
    DEFAULT_INCOME_CATEGORY,
    FLOW_TYPES,
    load_rules,
)

router = APIRouter(prefix="/api", tags=["transactions"])
Store = Annotated[FinanceDataStore, Depends(get_store)]

TRANSACTION_COLUMNS = list(Transaction.model_fields)
MAX_PAGE_SIZE = 5000


def select_transaction_columns(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Keep the API columns with plain (non categorical) dtypes."""
    return df_transactions[TRANSACTION_COLUMNS].astype(
        {"account": "string", "flow_type": "string"}
    )


def filter_transactions(
    df_transactions: pd.DataFrame,
    list_accounts: list[str] | None,
    list_categories: list[str] | None,
    list_flow_types: list[str] | None,
    search_text: str | None,
) -> pd.DataFrame:
    """Apply the optional list filters and a case-insensitive text search.

    Args:
        df_transactions: Categorized transactions.
        list_accounts: Accounts to keep.
        list_categories: Categories to keep.
        list_flow_types: Flow types to keep.
        search_text: Text searched in description and details.

    Returns:
        The matching transactions.
    """
    is_kept = pd.Series(True, index=df_transactions.index)
    for column, list_values in [
        ("account", list_accounts),
        ("category", list_categories),
        ("flow_type", list_flow_types),
    ]:
        if list_values:
            is_kept &= df_transactions[column].astype("string").isin(list_values)
    if search_text:
        series_text = (
            df_transactions["description"].fillna("")
            + " "
            + df_transactions["details"].fillna("")
        )
        is_kept &= series_text.str.contains(search_text, case=False, regex=False)
    return df_transactions[is_kept.fillna(False)]


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    store: Store,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    account: Annotated[list[str] | None, Query()] = None,
    category: Annotated[list[str] | None, Query()] = None,
    flow_type: Annotated[list[str] | None, Query()] = None,
    q: Annotated[str | None, Query(description="Text search")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Filtered transactions, newest first."""
    df_filtered = filter_transactions(
        filter_date_range(
            store.df_transactions, to_timestamp(date_from), to_timestamp(date_to)
        ),
        account,
        category,
        flow_type,
        q,
    ).iloc[::-1]
    return {
        "total": len(df_filtered),
        "items": dataframe_to_records(
            select_transaction_columns(df_filtered.iloc[offset : offset + limit])
        ),
    }


@router.get("/transactions/{transaction_key}", response_model=list[Transaction])
def get_transaction_with_counterpart(store: Store, transaction_key: str) -> list[dict]:
    """A transaction followed by its transfer counterpart, if it has one."""
    df_transactions = store.df_transactions
    df_match = df_transactions[df_transactions["transaction_key"] == transaction_key]
    if df_match.empty:
        raise HTTPException(status_code=404, detail="Transaction not found")
    counterparty_key = df_match["transfer_counterparty_key"].iloc[0]
    if pd.notna(counterparty_key):
        df_match = pd.concat(
            [
                df_match,
                df_transactions[df_transactions["transaction_key"] == counterparty_key],
            ]
        )
    return dataframe_to_records(select_transaction_columns(df_match))


@router.patch("/transactions/{transaction_key}/category", response_model=Transaction)
def update_transaction_category(
    store: Store, transaction_key: str, category_update: CategoryUpdate
) -> dict:
    """Manually set the category (and optionally the flow type) of a transaction."""
    if category_update.flow_type is not None and (
        category_update.flow_type not in FLOW_TYPES
    ):
        raise HTTPException(status_code=422, detail="Unknown flow_type")
    try:
        series_updated = store.update_category(
            transaction_key, category_update.category, category_update.flow_type
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Transaction not found") from error
    return dataframe_to_records(
        select_transaction_columns(series_updated.to_frame().T)
    )[0]


@router.get("/categories", response_model=CategoryCatalog)
def get_categories(store: Store) -> dict:
    """Categories from the rules, the defaults and the current data."""
    set_categories = {
        rule.category for rule in load_rules(store.path_rules, store.dict_placeholders)
    }
    set_categories |= {DEFAULT_EXPENSE_CATEGORY, DEFAULT_INCOME_CATEGORY}
    set_categories |= set(store.df_transactions["category"].dropna())
    return {"categories": sorted(set_categories), "flow_types": FLOW_TYPES}
