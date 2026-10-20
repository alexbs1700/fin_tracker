"""Fixtures for API tests: a data store over the synthetic extracts."""

import pytest
from fastapi.testclient import TestClient

from fin_tracker.api import FinanceDataStore, create_app
from fin_tracker.config import PATH_CATEGORY_RULES
from tests.conftest import FAKE_TODAY, TEST_OWNER_NAME


@pytest.fixture
def store(path_raw_data, tmp_path, fake_yfinance) -> FinanceDataStore:
    """Store over the synthetic extracts, real rules and a temporary overrides file."""
    return FinanceDataStore(
        path_raw_data=path_raw_data,
        path_rules=PATH_CATEGORY_RULES,
        path_overrides=tmp_path / "overrides.csv",
        dict_placeholders={"owner_name": TEST_OWNER_NAME},
        end_date=FAKE_TODAY,
    )


# Requests from the Mac itself: no access key needed
LOOPBACK_CLIENT = ("127.0.0.1", 50000)
TEST_ACCESS_KEY = "test-access-key-123"


@pytest.fixture
def client(store) -> TestClient:
    return TestClient(
        create_app(store, access_key=TEST_ACCESS_KEY, path_frontend_dist=None),
        client=LOOPBACK_CLIENT,
    )
