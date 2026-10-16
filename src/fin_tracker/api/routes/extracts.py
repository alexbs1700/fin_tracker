"""Extract endpoints: see what is loaded, validate an upload, replace an extract."""

import dataclasses
import datetime
import json
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from fin_tracker.api.dependencies import get_store
from fin_tracker.api.models import (
    ExtractReplaceResult,
    ExtractReportModel,
    ExtractStatus,
)
from fin_tracker.api.serialization import to_json_value
from fin_tracker.api.store import FinanceDataStore
from fin_tracker.ingestion.banks import BANKS, Bank, get_bank
from fin_tracker.ingestion.validation import (
    ExtractReport,
    load_summary,
    validate_extract,
)
from fin_tracker.storage.extracts import replace_extract

router = APIRouter(prefix="/api/extracts", tags=["extracts"])
Store = Annotated[FinanceDataStore, Depends(get_store)]

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def get_bank_or_404(bank_key: str) -> Bank:
    """Resolve the bank of the URL, answering 404 for unknown ones."""
    try:
        return get_bank(bank_key)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def report_to_dict(report: ExtractReport) -> dict:
    """Serialize a report to plain JSON values, including its computed ``is_valid``.

    It must be JSON-safe on its own because it also travels inside a 422 error.
    """
    return json.loads(
        json.dumps(
            {**dataclasses.asdict(report), "is_valid": report.is_valid},
            default=to_json_value,
        )
    )


async def validate_upload(
    bank: Bank, upload: UploadFile, path_current: Path, path_folder: Path
) -> tuple[ExtractReport, Path]:
    """Save the upload with the bank's extension and validate it.

    Args:
        bank: Bank the upload is for.
        upload: The uploaded file.
        path_current: Extract it would replace.
        path_folder: Temporary folder to save the upload in.

    Returns:
        The report and the path of the saved upload.

    Raises:
        HTTPException: 413 if the file is too large.
    """
    file_bytes = await upload.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El fichero supera los 20 MB")

    path_upload = path_folder / f"upload{bank.extension}"
    path_upload.write_bytes(file_bytes)

    upload_extension = Path(upload.filename or "").suffix.lower()
    if upload_extension != bank.extension:
        report = ExtractReport(
            bank=bank.key, current_summary=load_summary(bank, path_current)
        )
        report.errors.append(
            f"Un extracto de {bank.label} debe ser {bank.extension}, no "
            f"{upload_extension or 'un fichero sin extensión'}."
        )
        return report, path_upload
    return validate_extract(bank, path_upload, path_current), path_upload


@router.get("", response_model=list[ExtractStatus])
def list_extracts(store: Store) -> list[dict]:
    """The extract currently loaded for every bank."""
    list_statuses = []
    for bank in BANKS.values():
        path_file = store.path_raw_data / bank.file_name
        summary = load_summary(bank, path_file)
        list_statuses.append(
            {
                "bank": bank.key,
                "label": bank.label,
                "file_name": bank.file_name,
                "extension": bank.extension,
                "exists": path_file.exists(),
                "modified_at": datetime.datetime.fromtimestamp(
                    path_file.stat().st_mtime
                )
                if path_file.exists()
                else None,
                "summary": dataclasses.asdict(summary) if summary else None,
            }
        )
    return list_statuses


@router.post("/{bank_key}/validate", response_model=ExtractReportModel)
async def validate_extract_upload(
    store: Store, bank_key: str, file: UploadFile
) -> dict:
    """Check an upload against the bank's parsing rules without changing anything."""
    bank = get_bank_or_404(bank_key)
    with tempfile.TemporaryDirectory() as folder:
        report, _ = await validate_upload(
            bank, file, store.path_raw_data / bank.file_name, Path(folder)
        )
    return report_to_dict(report)


@router.post("/{bank_key}", response_model=ExtractReplaceResult)
async def replace_extract_upload(store: Store, bank_key: str, file: UploadFile) -> dict:
    """Validate the upload again and, if valid, replace the extract and reload."""
    bank = get_bank_or_404(bank_key)
    with tempfile.TemporaryDirectory() as folder:
        report, path_upload = await validate_upload(
            bank, file, store.path_raw_data / bank.file_name, Path(folder)
        )
        if not report.is_valid:
            raise HTTPException(status_code=422, detail=report_to_dict(report))
        path_backup = replace_extract(bank, path_upload, store.path_raw_data)

    store.reload()
    return {
        "report": report_to_dict(report),
        "backup_file": path_backup.name if path_backup else None,
    }
