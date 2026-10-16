"""Tests for fin_tracker.api.routes.net_worth (yfinance is faked)."""

import pytest

from tests.conftest import TR_EXPECTED_CASH_EUR

# 980 BBVA + 101.01 Revolut + TR cash
EXPECTED_CASH_EUR = 980.0 + 101.01 + TR_EXPECTED_CASH_EUR


def test_get_net_worth(client):
    dict_body = client.get("/api/net-worth").json()

    assert dict_body["cash_eur"] == pytest.approx(EXPECTED_CASH_EUR)
    assert dict_body["investments_eur"] == pytest.approx(72.0)
    assert dict_body["total_eur"] == pytest.approx(EXPECTED_CASH_EUR + 72.0)
    dict_joint = next(
        wallet
        for wallet in dict_body["cash_wallets"]
        if wallet["sub_account"] == "Cuenta Conjunta (EUR)"
    )
    assert dict_joint["my_balance_eur"] == 0.0


def test_get_net_worth_history_daily_and_monthly(client):
    list_daily = client.get(
        "/api/net-worth/history", params={"date_from": "2026-10-14"}
    ).json()
    list_monthly = client.get(
        "/api/net-worth/history", params={"frequency": "M"}
    ).json()

    assert [point["date"] for point in list_daily] == ["2026-10-14", "2026-10-15"]
    assert list_daily[-1]["total_eur"] == pytest.approx(EXPECTED_CASH_EUR + 72.0)
    assert list_monthly[-1]["date"] == "2026-10-15"
    assert len({point["date"][:7] for point in list_monthly}) == len(list_monthly)


def test_get_net_worth_history_by_account(client):
    list_points = client.get(
        "/api/net-worth/history/accounts",
        params={"date_from": "2026-10-15", "date_to": "2026-10-15"},
    ).json()
    assert {(point["account"], point["asset_type"]) for point in list_points} == {
        ("bbva", "cash"),
        ("revolut", "cash"),
        ("trade_republic", "cash"),
        ("trade_republic", "investments"),
    }


def test_get_net_worth_history_rejects_unknown_frequency(client):
    assert client.get("/api/net-worth/history?frequency=Y").status_code == 422


def test_get_net_worth_monthly_stats(client):
    list_stats = client.get(
        "/api/net-worth/monthly-stats",
        params={"value": "investments", "date_from": "2026-09-01"},
    ).json()

    assert [row["month"] for row in list_stats] == ["2026-09", "2026-10"]
    # Constant fake prices: the investments never move within a month
    assert list_stats[0]["min_eur"] == pytest.approx(72.0)
    assert list_stats[0]["max_eur"] == pytest.approx(72.0)
    assert list_stats[1]["is_partial"] is True
    assert client.get("/api/net-worth/monthly-stats?value=debt").status_code == 422
