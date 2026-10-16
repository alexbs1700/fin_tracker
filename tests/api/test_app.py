"""Tests for fin_tracker.api.app and fin_tracker.api.dependencies."""

import datetime

import pandas as pd

from fin_tracker.api import app as app_module
from fin_tracker.api.app import API_HOST, API_PORT, create_app
from fin_tracker.api.dependencies import get_store, to_timestamp


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_reload_drops_cached_data(client, store):
    df_first = store.df_raw_transactions
    assert client.post("/api/reload").json() == {"status": "reloaded"}
    assert store.df_raw_transactions is not df_first


def test_cors_allows_the_vite_dev_server(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_get_store_returns_the_app_store(store):
    app = create_app(store)

    class FakeRequest:
        pass

    request = FakeRequest()
    request.app = app
    assert get_store(request) is store


def test_to_timestamp():
    assert to_timestamp(None) is None
    assert to_timestamp(datetime.date(2026, 1, 2)) == pd.Timestamp("2026-01-02")


def test_run_serves_on_localhost(monkeypatch):
    dict_run_arguments = {}
    monkeypatch.setattr(
        app_module.uvicorn,
        "run",
        lambda app, host, port: dict_run_arguments.update(host=host, port=port),
    )
    app_module.run()
    assert dict_run_arguments == {"host": API_HOST, "port": API_PORT}
