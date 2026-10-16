"""Tests for the fin-tracker entry point."""

import pytest

import fin_tracker
from fin_tracker.ingestion import load_all_transactions


@pytest.mark.usefixtures("fake_yfinance")
def test_main_prints_net_worth(path_raw_data, monkeypatch, capsys):
    monkeypatch.setattr(
        fin_tracker,
        "load_all_transactions",
        lambda: load_all_transactions(path_raw_data),
    )
    fin_tracker.main()

    # 980 BBVA + 101.01 Revolut + 909.5 TR cash + 72 investments
    assert "Net worth: 2,062.51 €" in capsys.readouterr().out
