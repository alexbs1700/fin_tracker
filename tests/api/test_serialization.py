"""Tests for fin_tracker.api.serialization."""

import numpy as np
import pandas as pd
import pytest

from fin_tracker.api.serialization import (
    dataframe_to_records,
    filter_date_range,
    resample_last,
    to_json_value,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (pd.NA, None),
        (pd.NaT, None),
        (float("nan"), None),
        (np.float64("nan"), None),
        (pd.Timestamp("2026-01-02 10:00"), "2026-01-02"),
        (np.int64(3), 3),
        (np.bool_(True), True),
        ("text", "text"),
    ],
)
def test_to_json_value(value, expected):
    assert to_json_value(value) == expected


def test_dataframe_to_records():
    df_values = pd.DataFrame(
        {"date": pd.to_datetime(["2026-01-01"]), "value": [np.nan], "name": ["a"]}
    )
    assert dataframe_to_records(df_values) == [
        {"date": "2026-01-01", "value": None, "name": "a"}
    ]


@pytest.fixture
def df_daily():
    index_days = pd.date_range("2026-01-01", "2026-02-10", freq="D")
    return pd.DataFrame(
        {
            "date": list(index_days) * 2,
            "account": ["a"] * len(index_days) + ["b"] * len(index_days),
            "value_eur": list(range(len(index_days))) * 2,
        }
    )


def test_filter_date_range_is_inclusive(df_daily):
    df_filtered = filter_date_range(
        df_daily, pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-06")
    )
    assert df_filtered["date"].dt.day.unique().tolist() == [5, 6]
    assert filter_date_range(df_daily, None, None).equals(df_daily)


def test_resample_last_keeps_last_day_of_each_month_per_group(df_daily):
    df_monthly = resample_last(df_daily, "M", ["account"])
    assert df_monthly["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-31",
        "2026-01-31",
        "2026-02-10",
        "2026-02-10",
    ]
    assert df_monthly["account"].tolist() == ["a", "b", "a", "b"]


def test_resample_last_weekly_and_daily(df_daily):
    df_single = df_daily[df_daily["account"] == "a"]
    assert len(resample_last(df_single, "W")) == 7
    assert resample_last(df_single, "D").equals(df_single)


def test_resample_last_rejects_unknown_frequency(df_daily):
    with pytest.raises(ValueError, match="frequency"):
        resample_last(df_daily, "Y")
