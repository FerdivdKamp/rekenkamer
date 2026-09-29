"""Persistent upload and validation metadata."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class MetadataStore:
    """A local SQLite store for the immutable-workbook intake audit trail."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialise(self) -> None:
        """Create the metadata database and its schema when needed."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    upload_id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    source_organisation TEXT,
                    checksum TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    raw_file_location TEXT NOT NULL,
                    report_location TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS uploads_checksum ON uploads(checksum)")

    def record_upload(self, metadata: Mapping[str, Any]) -> None:
        """Persist one completed upload's metadata."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO uploads (
                    upload_id, original_filename, source_organisation, checksum,
                    schema_version, received_at, processed_at, validation_status,
                    raw_file_location, report_location
                ) VALUES (
                    :upload_id, :original_filename, :source_organisation, :checksum,
                    :schema_version, :received_at, :processed_at, :validation_status,
                    :raw_file_location, :report_location
                )
                """,
                metadata,
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)
