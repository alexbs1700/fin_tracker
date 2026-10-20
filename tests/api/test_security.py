"""Tests for fin_tracker.api.security."""

import pytest
from fastapi.testclient import TestClient

from fin_tracker.api import create_app
from fin_tracker.api.security import (
    ACCESS_KEY_HEADER,
    is_access_key_valid,
    is_loopback,
    validate_exposure,
)
from tests.api.conftest import TEST_ACCESS_KEY

PHONE_CLIENT = ("192.168.1.50", 50000)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("localhost", True),
        ("192.168.1.50", False),
        ("testclient", False),
        (None, False),
    ],
)
def test_is_loopback(host, expected):
    assert is_loopback(host) is expected


def test_is_access_key_valid():
    assert is_access_key_valid("secret-key", "secret-key")
    assert not is_access_key_valid("wrong", "secret-key")
    assert not is_access_key_valid(None, "secret-key")
    # No configured key never authorizes a remote client
    assert not is_access_key_valid("", "")


def test_validate_exposure():
    validate_exposure("127.0.0.1", "")
    validate_exposure("0.0.0.0", "a-long-enough-key")
    with pytest.raises(SystemExit, match="FIN_TRACKER_ACCESS_KEY"):
        validate_exposure("0.0.0.0", "short")


@pytest.fixture
def phone(store) -> TestClient:
    """A client on the home network, not the Mac."""
    return TestClient(
        create_app(store, access_key=TEST_ACCESS_KEY, path_frontend_dist=None),
        client=PHONE_CLIENT,
    )


def test_remote_client_needs_the_access_key(phone):
    assert phone.get("/api/session").status_code == 401
    assert (
        phone.get("/api/net-worth", headers={ACCESS_KEY_HEADER: "wrong"}).status_code
        == 401
    )
    assert phone.get(
        "/api/session", headers={ACCESS_KEY_HEADER: TEST_ACCESS_KEY}
    ).json() == {"authorized": True}


def test_health_stays_public_and_loopback_needs_no_key(phone, client):
    assert phone.get("/api/health").status_code == 200
    assert client.get("/api/session").status_code == 200
