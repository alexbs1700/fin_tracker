"""Tests for fin_tracker.api.routes.extracts."""

import pandas as pd
import pytest
from fastapi import HTTPException

from fin_tracker.api.routes import extracts as extracts_routes
from fin_tracker.api.routes.extracts import get_bank_or_404, report_to_dict
from fin_tracker.ingestion.validation import ExtractReport, ExtractSummary
from fin_tracker.storage.extracts import BACKUP_FOLDER_NAME


def upload(path_file, file_name=None):
    """Multipart payload for the TestClient."""
    return {"file": (file_name or path_file.name, path_file.read_bytes())}


def test_get_bank_or_404():
    assert get_bank_or_404("bbva").key == "bbva"
    with pytest.raises(HTTPException) as error:
        get_bank_or_404("ing")
    assert error.value.status_code == 404


def test_report_to_dict_is_json_safe_and_includes_validity():
    report = ExtractReport(
        bank="bbva",
        errors=["x"],
        summary=ExtractSummary(
            1, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")
        ),
    )
    dict_report = report_to_dict(report)
    assert dict_report["is_valid"] is False
    assert dict_report["summary"]["date_from"] == "2026-01-01"


def test_list_extracts(client):
    list_statuses = client.get("/api/extracts").json()
    assert [status["bank"] for status in list_statuses] == [
        "bbva",
        "revolut",
        "trade_republic",
    ]
    assert all(status["exists"] for status in list_statuses)
    assert list_statuses[2]["summary"]["rows"] == 5


def test_validate_does_not_touch_the_current_extract(client, path_raw_data):
    path_file = path_raw_data / "tr_full_data.csv"
    content_before = path_file.read_bytes()
    report = client.post(
        "/api/extracts/trade_republic/validate", files=upload(path_file)
    ).json()

    assert report["is_valid"] is True
    assert path_file.read_bytes() == content_before


def test_validate_rejects_wrong_extension_and_unknown_bank(client, path_raw_data):
    report = client.post(
        "/api/extracts/bbva/validate", files=upload(path_raw_data / "tr_full_data.csv")
    ).json()
    assert report["is_valid"] is False
    assert ".xlsx" in report["errors"][0]
    assert (
        client.post(
            "/api/extracts/ing/validate",
            files=upload(path_raw_data / "tr_full_data.csv"),
        ).status_code
        == 404
    )


def test_replace_valid_extract_backs_up_and_reloads(client, store, path_raw_data):
    df_before = store.df_raw_transactions
    path_file = path_raw_data / "revolut_full_data.csv"
    dict_body = client.post("/api/extracts/revolut", files=upload(path_file)).json()

    assert dict_body["report"]["is_valid"] is True
    assert (path_raw_data / BACKUP_FOLDER_NAME / dict_body["backup_file"]).exists()
    assert store.df_raw_transactions is not df_before


def test_replace_invalid_extract_is_refused(client, path_raw_data):
    path_target = path_raw_data / "revolut_full_data.csv"
    content_before = path_target.read_bytes()
    response = client.post(
        "/api/extracts/revolut",
        files=upload(path_raw_data / "tr_full_data.csv", "revolut.csv"),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["is_valid"] is False
    assert path_target.read_bytes() == content_before
    assert not (path_raw_data / BACKUP_FOLDER_NAME).exists()


def test_upload_too_large(client, path_raw_data, monkeypatch):
    monkeypatch.setattr(extracts_routes, "MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/api/extracts/trade_republic/validate",
        files=upload(path_raw_data / "tr_full_data.csv"),
    )
    assert response.status_code == 413
