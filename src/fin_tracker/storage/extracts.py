"""Replacing the bank extracts in ``data/raw`` safely, keeping a backup."""

import shutil
from pathlib import Path

import pandas as pd

from fin_tracker.ingestion.banks import Bank

BACKUP_FOLDER_NAME = "backups"


def backup_extract(path_current: Path, path_raw_data: Path) -> Path | None:
    """Copy the current extract to ``data/raw/backups`` with a timestamp.

    Args:
        path_current: Extract about to be replaced.
        path_raw_data: Raw data folder.

    Returns:
        Path of the backup, or None if there was no current extract.
    """
    if not path_current.exists():
        return None
    path_backups = path_raw_data / BACKUP_FOLDER_NAME
    path_backups.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d-%H%M%S")
    path_backup = path_backups / f"{path_current.stem}.{timestamp}{path_current.suffix}"
    shutil.copy2(path_current, path_backup)
    return path_backup


def replace_extract(bank: Bank, path_upload: Path, path_raw_data: Path) -> Path | None:
    """Back up the bank's current extract and put the upload in its place.

    The upload is copied next to the target first and then renamed over it, so
    the app never sees a half-written extract.

    Args:
        bank: Bank whose extract is replaced.
        path_upload: Validated uploaded file.
        path_raw_data: Raw data folder.

    Returns:
        Path of the backup of the previous extract, or None if there was none.
    """
    path_raw_data.mkdir(parents=True, exist_ok=True)
    path_target = path_raw_data / bank.file_name
    path_backup = backup_extract(path_target, path_raw_data)
    path_staging = path_target.with_name(f".{path_target.name}.uploading")
    shutil.copyfile(path_upload, path_staging)
    path_staging.replace(path_target)
    return path_backup
