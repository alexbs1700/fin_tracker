"""Tests for fin_tracker.api.routes.transactions."""

import datetime

import pytest

from fin_tracker.api.routes.transactions import (
    TransactionFilters,
    filter_transactions,
    select_transaction_columns,
)
from tests.conftest import TEST_OWNER_NAME, build_transactions


@pytest.fixture
def store_with_transfer(store):
    """Store seeded with a BBVA -> Revolut transfer and two expenses."""
    owner = TEST_OWNER_NAME.upper()
    df_transactions = build_transactions(
        [
            {"date": "2026-01-01", "account": "bbva", "amount": -500.0, "description": "Transferencia realizada", "transaction_type": "La pasta del mes"},
            {"date": "2026-01-02", "account": "revolut", "sub_account": "Cuenta personal (EUR)", "amount": 500.0, "description": f"Pago de {owner}"},
            {"date": "2026-01-03", "account": "bbva", "amount": -20.0, "description": "Mercadona", "details": "Madrid"},
            {"date": "2026-01-04", "account": "revolut", "sub_account": "Cuenta personal (EUR)", "amount": -9.0, "description": "Teatro Real"},
        ]
    )  # fmt: skip
    store.get_cached("df_raw_transactions", lambda: df_transactions)
    return store


def test_filter_transactions_by_lists_and_text(store_with_transfer):
    df_transactions = store_with_transfer.df_transactions
    assert len(filter_transactions(df_transactions, ["bbva"], None, None, None)) == 2
    assert len(filter_transactions(df_transactions, None, ["Ocio"], None, None)) == 1
    assert (
        len(
            filter_transactions(
                df_transactions, None, None, ["internal_transfer"], None
            )
        )
        == 2
    )
    assert len(filter_transactions(df_transactions, None, None, None, "madrid")) == 1


def test_select_transaction_columns_uses_plain_dtypes(store_with_transfer):
    df_selected = select_transaction_columns(store_with_transfer.df_transactions)
    assert df_selected["flow_type"].dtype == "string"
    assert "pair_transfer" not in df_selected.columns


def test_list_transactions_newest_first_with_pagination(client, store_with_transfer):
    dict_body = client.get("/api/transactions", params={"limit": 2, "offset": 1}).json()
    assert dict_body["total"] == 4
    assert [item["date"] for item in dict_body["items"]] == ["2026-01-03", "2026-01-02"]


def test_list_transactions_filters(client, store_with_transfer):
    dict_body = client.get(
        "/api/transactions",
        params={"flow_type": ["expense"], "date_from": "2026-01-04"},
    ).json()
    assert [item["description"] for item in dict_body["items"]] == ["Teatro Real"]


def test_transaction_detail_includes_transfer_counterpart(client, store_with_transfer):
    transaction_key = store_with_transfer.df_transactions["transaction_key"].iloc[0]
    list_legs = client.get(f"/api/transactions/{transaction_key}").json()

    assert [leg["account"] for leg in list_legs] == ["bbva", "revolut"]
    assert list_legs[0]["transfer_id"] == list_legs[1]["transfer_id"] is not None


def test_transaction_detail_404(client, store_with_transfer):
    assert client.get("/api/transactions/missing").status_code == 404


def test_update_category(client, store_with_transfer):
    transaction_key = store_with_transfer.df_transactions["transaction_key"].iloc[3]
    dict_body = client.patch(
        f"/api/transactions/{transaction_key}/category", json={"category": "Regalos"}
    ).json()
    assert dict_body["category"] == "Regalos"
    assert dict_body["is_category_override"] is True
    assert dict_body["flow_type"] == "expense"


def test_update_category_errors(client, store_with_transfer):
    transaction_key = store_with_transfer.df_transactions["transaction_key"].iloc[3]
    assert (
        client.patch(
            f"/api/transactions/{transaction_key}/category",
            json={"category": "X", "flow_type": "gift"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/transactions/missing/category", json={"category": "X"}
        ).status_code
        == 404
    )


def test_get_categories(client, store_with_transfer):
    dict_body = client.get("/api/categories").json()
    assert {"Supermercado", "Otros gastos", "Traspaso interno"} <= set(
        dict_body["categories"]
    )
    assert dict_body["categories"] == sorted(dict_body["categories"])
    assert "internal_transfer" in dict_body["flow_types"]


def test_categories_include_manual_ones(client, store_with_transfer):
    transaction_key = store_with_transfer.df_transactions["transaction_key"].iloc[3]
    client.patch(
        f"/api/transactions/{transaction_key}/category", json={"category": "Regalos"}
    )
    assert "Regalos" in client.get("/api/categories").json()["categories"]


def test_transaction_filters_apply_every_filter(store_with_transfer):
    filters = TransactionFilters(
        date_from=datetime.date(2026, 1, 2), account=["revolut"], flow_type=["expense"]
    )
    df_filtered = filters.apply(store_with_transfer.df_transactions)
    assert df_filtered["description"].tolist() == ["Teatro Real"]


def test_summarize_transactions_follows_the_filters(client, store_with_transfer):
    list_total = client.get(
        "/api/transactions/summary",
        params={"flow_type": ["expense", "internal_transfer"]},
    ).json()
    assert list_total == [
        {
            "month": None,
            "category": None,
            "merchant": None,
            "flow_type": None,
            "inflow_eur": 500.0,
            "outflow_eur": 529.0,
            "net_eur": -29.0,
            "transactions": 4,
        }
    ]

    list_by_category = client.get(
        "/api/transactions/summary",
        params={"group_by": "category", "account": "bbva", "flow_type": "expense"},
    ).json()
    assert [(row["category"], row["net_eur"]) for row in list_by_category] == [
        ("Supermercado", -20.0)
    ]
    assert client.get("/api/transactions/summary?group_by=weekday").status_code == 422
