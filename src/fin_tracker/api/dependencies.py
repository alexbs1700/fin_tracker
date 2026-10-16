"""Shared FastAPI dependencies and query parameter types."""

import datetime
from typing import Annotated, Literal

import pandas as pd
from fastapi import Query, Request

from fin_tracker.api.store import FinanceDataStore

DateFrom = Annotated[datetime.date | None, Query(description="First day, inclusive")]
DateTo = Annotated[datetime.date | None, Query(description="Last day, inclusive")]
Frequency = Annotated[
    Literal["D", "W", "M"], Query(description="Daily, weekly or monthly points")
]


def get_store(request: Request) -> FinanceDataStore:
    """Return the data store attached to the running app."""
    return request.app.state.store


def to_timestamp(date: datetime.date | None) -> pd.Timestamp | None:
    """Convert an optional query date to a pandas timestamp."""
    return pd.Timestamp(date) if date is not None else None
