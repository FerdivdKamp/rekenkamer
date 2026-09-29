import json
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from rekenkamer_pipeline.api import create_app


def write_schema(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "api-test-v1",
                "sheets": {"Data": {"columns": {"Name": "string", "Amount": "number"}}},
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
    schema = tmp_path / "schema.json"
    write_schema(schema)
    return TestClient(
        create_app(
            upload_directory=tmp_path / "uploads",
            schema_path=schema,
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
    stored_files = list((tmp_path / "uploads").glob("*.xlsx"))
    assert [path.name for path in stored_files] == [f"{body['upload_id']}.xlsx"]


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
