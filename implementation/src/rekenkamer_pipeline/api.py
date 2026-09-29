"""Small synchronous HTTP API for workbook validation."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status

from .metadata import MetadataStore
from .validation import SchemaError, validate_workbook

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
DEFAULT_SCHEMA_PATH = Path(__file__).with_name("service_schema.json")


def _path_from_environment(name: str, default: Path) -> Path:
    """Return a path configured by an optional environment variable."""
    return Path(os.environ.get(name, default))


def _max_upload_bytes_from_environment() -> int:
    """Return the configured positive upload limit."""
    value = os.environ.get("REKENKAMER_MAX_UPLOAD_BYTES")
    if value is None:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        limit = int(value)
    except ValueError as error:
        raise ValueError("REKENKAMER_MAX_UPLOAD_BYTES must be an integer.") from error
    if limit <= 0:
        raise ValueError("REKENKAMER_MAX_UPLOAD_BYTES must be greater than zero.")
    return limit


def create_app(
    *,
    upload_directory: Path | None = None,
    metadata_directory: Path | None = None,
    schema_path: Path | None = None,
    max_upload_bytes: int | None = None,
) -> FastAPI:
    """Create the API application with local-development configuration."""
    configured_upload_directory = upload_directory or _path_from_environment(
        "REKENKAMER_UPLOAD_DIRECTORY", Path("uploads")
    )
    configured_schema_path = schema_path or _path_from_environment(
        "REKENKAMER_SCHEMA_PATH", DEFAULT_SCHEMA_PATH
    )
    configured_metadata_directory = metadata_directory or _path_from_environment(
        "REKENKAMER_METADATA_DIRECTORY", configured_upload_directory / "metadata"
    )
    configured_max_upload_bytes = (
        _max_upload_bytes_from_environment() if max_upload_bytes is None else max_upload_bytes
    )
    if configured_max_upload_bytes <= 0:
        raise ValueError("max_upload_bytes must be greater than zero.")

    app = FastAPI(title="Rekenkamer data pipeline API")
    metadata_store = MetadataStore(configured_metadata_directory / "uploads.sqlite3")
    raw_directory = configured_upload_directory / "raw"
    report_directory = configured_upload_directory / "reports"

    @app.get("/health")
    def health() -> dict[str, str]:
        """Provide a configuration-free deployment health response."""
        return {"status": "ok"}

    @app.post("/uploads", status_code=status.HTTP_201_CREATED)
    async def upload_workbook(
        file: Annotated[UploadFile, File(...)],
        source_organisation: Annotated[str | None, Form()] = None,
    ) -> dict[str, object]:
        """Store a workbook and synchronously return its validation report."""
        supplied_filename = file.filename or ""
        if Path(supplied_filename).suffix.lower() != ".xlsx":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only .xlsx files are supported.",
            )

        upload_id = uuid4().hex
        raw_directory.mkdir(parents=True, exist_ok=True)
        temporary_destination = raw_directory / f".{upload_id}.part"
        uploaded_size = 0
        checksum = hashlib.sha256()
        try:
            with temporary_destination.open("xb") as stored_file:
                while chunk := await file.read(CHUNK_SIZE):
                    uploaded_size += len(chunk)
                    if uploaded_size > configured_max_upload_bytes:
                        stored_file.close()
                        temporary_destination.unlink(missing_ok=True)
                        try:
                            raw_directory.rmdir()
                        except OSError:
                            # Another upload can legitimately be staging in this directory.
                            pass
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"Upload exceeds the {configured_max_upload_bytes}-byte size limit.",
                        )
                    stored_file.write(chunk)
                    checksum.update(chunk)
        finally:
            await file.close()

        content_checksum = checksum.hexdigest()
        destination = raw_directory / f"{content_checksum}.xlsx"
        try:
            # Creating a hard link fails if another upload already owns this checksum.
            # Unlike replace(), this can never overwrite the original raw workbook.
            os.link(temporary_destination, destination)
        except FileExistsError:
            pass
        finally:
            temporary_destination.unlink(missing_ok=True)

        try:
            report = validate_workbook(destination, configured_schema_path)
        except (OSError, SchemaError) as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Validation service is not configured correctly.",
            ) from error
        report["source_filename"] = supplied_filename
        report_directory.mkdir(parents=True, exist_ok=True)
        report_location = report_directory / f"{upload_id}.validation.json"
        report_location.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        processed_at = datetime.now(UTC).isoformat()
        metadata_store.initialise()
        metadata_store.record_upload(
            {
                "upload_id": upload_id,
                "original_filename": supplied_filename,
                "source_organisation": source_organisation,
                "checksum": f"sha256:{content_checksum}",
                "schema_version": report["schema_version"],
                "received_at": report["timestamp"],
                "processed_at": processed_at,
                "validation_status": report["status"],
                "raw_file_location": str(destination),
                "report_location": str(report_location),
            }
        )
        return {"upload_id": upload_id, "report": report}

    return app


app = create_app()
