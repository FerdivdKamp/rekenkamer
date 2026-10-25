import json
import sqlite3
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from rekenkamer_pipeline.api import create_app


def write_schema_registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schemas": [
                    {
                        "id": "audit-workbook",
                        "version": "api-test-v1",
                        "effective_from": "2026-01-01",
                        "effective_to": None,
                        "owner": "Financial Audit",
                        "definition": {
                            "version": "api-test-v1",
                            "sheets": {"Data": {"columns": {"Name": "string", "Amount": "number"}}},
                        },
                    },
                    {
                        "id": "audit-workbook",
                        "version": "api-test-v2",
                        "effective_from": "2026-10-01",
                        "effective_to": None,
                        "owner": "Financial Audit",
                        "definition": {
                            "version": "api-test-v2",
                            "sheets": {"Data": {"columns": {"Name": "string"}}},
                        },
                    },
                ],
                "defaults": {"default": {"id": "audit-workbook", "version": "api-test-v1"}},
            }
        ),
        encoding="utf-8",
    )


def workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Data"
    for row in rows:
        worksheet.append(row)
    # openpyxl accepts file-like objects, avoiding a user-controlled upload path in tests.
    contents = BytesIO()
    workbook.save(contents)
    return contents.getvalue()


def make_client(tmp_path: Path, *, max_upload_bytes: int = 1024 * 1024) -> TestClient:
    registry = tmp_path / "schema-registry.json"
    write_schema_registry(registry)
    return TestClient(
        create_app(
            upload_directory=tmp_path / "uploads",
            schema_registry_path=registry,
            max_upload_bytes=max_upload_bytes,
        )
    )


def test_health_returns_no_configuration(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_valid_workbook_returns_report_and_generated_storage_name(tmp_path: Path) -> None:
    response = make_client(tmp_path).post(
        "/uploads",
        files={"file": ("../../client-name.xlsx", workbook_bytes([["Name", "Amount"], ["Finance", 12]]))},
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["upload_id"]) == 32
    assert body["report"]["source_filename"] == "../../client-name.xlsx"
    assert body["report"]["status"] == "passed"
    stored_files = list((tmp_path / "uploads" / "raw").glob("*.xlsx"))
    assert len(stored_files) == 1

    database = tmp_path / "uploads" / "metadata" / "uploads.sqlite3"
    with sqlite3.connect(database) as connection:
        record = connection.execute(
            "SELECT * FROM uploads WHERE upload_id = ?", (body["upload_id"],)
        ).fetchone()
    assert record is not None
    assert record[1] == "../../client-name.xlsx"
    assert record[2] is None
    assert record[3].startswith("sha256:")
    assert record[4] == "audit-workbook"
    assert record[5] == "api-test-v1"
    assert record[8] == "passed"
    assert Path(record[9]) == stored_files[0]
    assert Path(record[10]).is_file()
    assert body["report"]["schema_id"] == "audit-workbook"
    assert body["report"]["schema_version"] == "api-test-v1"


def test_schemas_can_be_listed_retrieved_and_explicitly_selected(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    listed = client.get("/schemas")
    retrieved = client.get("/schemas/audit-workbook/versions/api-test-v2")
    upload = client.post(
        "/uploads",
        files={"file": ("v2.xlsx", workbook_bytes([["Name"], ["Finance"]]))},
        data={"schema_id": "audit-workbook", "schema_version": "api-test-v2"},
    )

    assert listed.status_code == retrieved.status_code == 200
    assert upload.status_code == 201
    assert {item["version"] for item in listed.json()["schemas"]} == {"api-test-v1", "api-test-v2"}
    assert retrieved.json()["definition"]["version"] == "api-test-v2"
    assert upload.json()["report"]["schema_id"] == "audit-workbook"
    assert upload.json()["report"]["schema_version"] == "api-test-v2"


def test_invalid_registry_definition_is_rejected_before_api_starts(tmp_path: Path) -> None:
    registry = tmp_path / "bad-registry.json"
    registry.write_text(
        json.dumps(
            {
                "schemas": [
                    {
                        "id": "bad",
                        "version": "1",
                        "effective_from": "2026-01-01",
                        "owner": "FA",
                        "definition": {"version": "1"},
                    }
                ],
                "defaults": {"default": {"id": "bad", "version": "1"}},
            }
        ),
        encoding="utf-8",
    )

    from rekenkamer_pipeline.schema_registry import SchemaRegistryError

    try:
        create_app(upload_directory=tmp_path / "uploads", schema_registry_path=registry)
    except SchemaRegistryError:
        pass
    else:
        raise AssertionError("Invalid registry definition should prevent activation.")


def test_invalid_readable_workbook_returns_failed_report(tmp_path: Path) -> None:
    response = make_client(tmp_path).post(
        "/uploads",
        files={"file": ("invalid.xlsx", workbook_bytes([["Name", "Other"], ["Finance", "x"]]))},
    )

    assert response.status_code == 201
    assert response.json()["report"]["status"] == "failed"
    assert {issue["code"] for issue in response.json()["report"]["issues"]} == {
        "missing_column",
        "unexpected_column",
    }
    database = tmp_path / "uploads" / "metadata" / "uploads.sqlite3"
    with sqlite3.connect(database) as connection:
        validation_status = connection.execute(
            "SELECT validation_status FROM uploads WHERE upload_id = ?",
            (response.json()["upload_id"],),
        ).fetchone()
    assert validation_status == ("failed",)


def test_unreadable_and_duplicate_uploads_are_persisted_without_replacing_raw_file(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    duplicate_bytes = workbook_bytes([["Name", "Amount"], ["Finance", 12]])

    first = client.post(
        "/uploads",
        files={"file": ("first.xlsx", duplicate_bytes)},
        data={"source_organisation": "Ministry of Finance"},
    )
    second = client.post("/uploads", files={"file": ("second.xlsx", duplicate_bytes)})
    unreadable = client.post(
        "/uploads", files={"file": ("broken.xlsx", b"not an Excel workbook")}
    )

    assert first.status_code == second.status_code == unreadable.status_code == 201
    assert unreadable.json()["report"]["status"] == "failed"
    database = tmp_path / "uploads" / "metadata" / "uploads.sqlite3"
    with sqlite3.connect(database) as connection:
        records = connection.execute(
            "SELECT original_filename, source_organisation, checksum, validation_status, "
            "raw_file_location FROM uploads ORDER BY rowid"
        ).fetchall()
    assert len(records) == 3
    assert records[0][1] == "Ministry of Finance"
    assert records[0][2] == records[1][2]
    assert records[0][4] == records[1][4]
    assert records[2][3] == "failed"
    assert len(list((tmp_path / "uploads" / "raw").glob("*.xlsx"))) == 2


def test_missing_or_non_excel_file_returns_client_error(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    assert client.post("/uploads").status_code == 422
    response = client.post("/uploads", files={"file": ("notes.txt", b"not an Excel workbook")})
    assert response.status_code == 415
    assert response.json()["detail"] == "Only .xlsx files are supported."


def test_oversized_upload_returns_client_error_and_is_not_stored(tmp_path: Path) -> None:
    client = make_client(tmp_path, max_upload_bytes=3)
    response = client.post("/uploads", files={"file": ("large.xlsx", b"1234")})

    assert response.status_code == 413
    assert not (tmp_path / "uploads").exists() or not list((tmp_path / "uploads").iterdir())
