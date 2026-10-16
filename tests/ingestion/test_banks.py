"""Tests for fin_tracker.ingestion.banks."""

import pytest

from fin_tracker.ingestion.banks import BANKS, get_bank


def test_get_bank_and_extension():
    assert get_bank("bbva").extension == ".xlsx"
    assert get_bank("revolut").extension == ".csv"
    assert get_bank("trade_republic").label == "Trade Republic"


def test_get_bank_rejects_unknown_keys():
    with pytest.raises(KeyError, match="expected one of"):
        get_bank("ing")


@pytest.mark.parametrize("bank_key", sorted(BANKS))
def test_every_bank_reads_its_synthetic_extract(path_raw_data, bank_key):
    bank = BANKS[bank_key]
    df_raw = bank.read_raw(path_raw_data / bank.file_name)
    assert set(bank.required_columns) <= set(df_raw.columns)
    assert (bank.normalize(df_raw)["account"] == bank_key).all()
