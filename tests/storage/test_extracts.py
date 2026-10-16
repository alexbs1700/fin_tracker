"""Tests for fin_tracker.storage.extracts."""

from fin_tracker.ingestion.banks import BANKS
from fin_tracker.storage.extracts import (
    BACKUP_FOLDER_NAME,
    backup_extract,
    replace_extract,
)


def test_backup_extract_copies_with_timestamp(tmp_path):
    assert backup_extract(tmp_path / "missing.csv", tmp_path) is None

    path_current = tmp_path / "tr_full_data.csv"
    path_current.write_text("old", encoding="utf-8")
    path_backup = backup_extract(path_current, tmp_path)

    assert path_backup.parent == tmp_path / BACKUP_FOLDER_NAME
    assert path_backup.name.startswith("tr_full_data.") and path_backup.suffix == ".csv"
    assert path_backup.read_text(encoding="utf-8") == "old"


def test_replace_extract_backs_up_and_overwrites(tmp_path):
    bank = BANKS["trade_republic"]
    path_raw_data = tmp_path / "raw"
    path_upload = tmp_path / "upload.csv"
    path_upload.write_text("new", encoding="utf-8")

    assert replace_extract(bank, path_upload, path_raw_data) is None
    path_upload.write_text("newer", encoding="utf-8")
    path_backup = replace_extract(bank, path_upload, path_raw_data)

    assert (path_raw_data / bank.file_name).read_text(encoding="utf-8") == "newer"
    assert path_backup.read_text(encoding="utf-8") == "new"
    assert not list(path_raw_data.glob(".*uploading"))
