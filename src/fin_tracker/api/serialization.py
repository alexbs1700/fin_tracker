"""Helpers to turn dataframes into JSON-friendly records."""

import math
from typing import Any

import pandas as pd

# Resampling frequencies accepted by the history endpoints (None keeps daily rows)
FREQUENCY_TO_PERIOD = {"D": None, "W": "W", "M": "M"}


def to_json_value(value: Any) -> Any:
    """Convert one cell to a JSON value: dates to ISO strings, missing to None."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "item"):
        # numpy scalars
        return to_json_value(value.item())
    return value


def dataframe_to_records(df_values: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a dataframe to a list of JSON-serializable dicts.

    Args:
        df_values: Any dataframe.

    Returns:
        One dict per row.
    """
    list_columns = list(df_values.columns)
    return [
        {
            column: to_json_value(value)
            for column, value in zip(list_columns, row, strict=True)
        }
        for row in df_values.itertuples(index=False, name=None)
    ]


def filter_date_range(
    df_values: pd.DataFrame,
    date_from: pd.Timestamp | None,
    date_to: pd.Timestamp | None,
    date_column: str = "date",
) -> pd.DataFrame:
    """Keep rows whose ``date_column`` falls inside the (inclusive) range."""
    if date_from is not None:
        df_values = df_values[df_values[date_column] >= date_from]
    if date_to is not None:
        df_values = df_values[df_values[date_column] <= date_to]
    return df_values


def resample_last(
    df_values: pd.DataFrame,
    frequency: str,
    list_group_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Keep the last row of every period, per group.

    Balances and values are stocks, so a week or month is represented by its
    last day (which is labelled with that last day, not the period end).

    Args:
        df_values: Daily rows with a ``date`` column.
        frequency: ``D``, ``W`` or ``M``.
        list_group_columns: Columns identifying each series.

    Returns:
        One row per period and group.

    Raises:
        ValueError: If the frequency is unknown.
    """
    if frequency not in FREQUENCY_TO_PERIOD:
        raise ValueError(f"Unknown frequency {frequency}")
    if FREQUENCY_TO_PERIOD[frequency] is None or df_values.empty:
        return df_values

    list_group_columns = list_group_columns or []
    series_period = df_values["date"].dt.to_period(FREQUENCY_TO_PERIOD[frequency])
    return (
        df_values.assign(period=series_period)
        .sort_values("date")
        .groupby([*list_group_columns, "period"], observed=True, dropna=False)
        .tail(1)
        .drop(columns="period")
        .sort_values(["date", *list_group_columns])
        .reset_index(drop=True)
    )
