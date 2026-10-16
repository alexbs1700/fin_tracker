"""Tests for fin_tracker.api.routes.portfolio (yfinance is faked)."""

import pytest


def test_get_portfolio(client):
    dict_body = client.get("/api/portfolio").json()

    # 6 shares left, FIFO cost 60.6, valued at 12
    assert dict_body["market_value_eur"] == pytest.approx(72.0)
    assert dict_body["cost_basis_eur"] == pytest.approx(60.6)
    assert dict_body["unrealized_return"] == pytest.approx(11.4 / 60.6)
    # Sold 4 for 59 net against a FIFO cost of 40.4
    assert dict_body["realized_gain_eur"] == pytest.approx(59.0 - 40.4)
    assert dict_body["allocation"] == {"equity": pytest.approx(1.0)}
    assert dict_body["positions"][0]["weight"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("breakdown", "expected_group"), [("total", None), ("bucket", "equity")]
)
def test_get_portfolio_history(client, breakdown, expected_group):
    list_points = client.get(
        "/api/portfolio/history",
        params={"breakdown": breakdown, "frequency": "M", "date_from": "2026-10-01"},
    ).json()
    assert list_points == [
        {
            "date": "2026-10-15",
            "group": expected_group,
            "cost_basis_eur": pytest.approx(60.6),
            "market_value_eur": pytest.approx(72.0),
        }
    ]


def test_get_portfolio_history_by_asset(client):
    list_points = client.get(
        "/api/portfolio/history",
        params={"breakdown": "asset", "date_from": "2026-10-15"},
    ).json()
    assert list_points[0]["group"] == "Test ETF"
