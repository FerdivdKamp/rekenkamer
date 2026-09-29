import json
from pathlib import Path

from openpyxl import Workbook

from rekenkamer_pipeline.cli import main
from rekenkamer_pipeline.validation import validate_workbook


def write_workbook(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(name)
        for row in rows:
            worksheet.append(row)
    workbook.save(path)


def write_schema(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "test-v1",
                "sheets": {
                    "Data": {"columns": {"Name": "string", "Amount": "number"}},
                },
            }
        ),
        encoding="utf-8",
    )


def test_valid_workbook_passes_and_writes_a_report(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    workbook = tmp_path / "valid.xlsx"
    report = tmp_path / "report.json"
    write_schema(schema)
    write_workbook(workbook, {"Data": [["Name", "Amount"], ["Finance", 12.5]]})

    exit_code = main(["validate", str(workbook), "--schema", str(schema), "--output", str(report)])

    assert exit_code == 0
    contents = json.loads(report.read_text(encoding="utf-8"))
    assert contents["source_filename"] == "valid.xlsx"
    assert contents["status"] == "passed"
    assert contents["issues"] == []
    assert contents["schema_version"] == "test-v1"
    assert contents["timestamp"].endswith("+00:00")


def test_single_workbook_uses_a_suffixless_output_path_as_a_directory(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    workbook = tmp_path / "valid.xlsx"
    output_directory = tmp_path / "reports"
    write_schema(schema)
    write_workbook(workbook, {"Data": [["Name", "Amount"], ["Finance", 12.5]]})

    exit_code = main(["validate", str(workbook), "--schema", str(schema), "--output", str(output_directory)])

    assert exit_code == 0
    report = json.loads((output_directory / "valid.validation.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"


def test_all_structural_problems_are_reported(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    workbook = tmp_path / "invalid.xlsx"
    write_schema(schema)
    write_workbook(workbook, {"Data": [["Name", "Extra"], [9, "ignored"]], "Other": [["Value"], [1]]})

    report = validate_workbook(workbook, schema)

    assert report["status"] == "failed"
    assert {issue["code"] for issue in report["issues"]} == {
        "missing_column",
        "unexpected_column",
        "column_type_mismatch",
        "unexpected_sheet",
    }


def test_batch_continues_after_an_unreadable_workbook(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    valid = tmp_path / "valid.xlsx"
    broken = tmp_path / "broken.xlsx"
    output_directory = tmp_path / "reports"
    write_schema(schema)
    write_workbook(valid, {"Data": [["Name", "Amount"], ["Finance", 10]]})
    broken.write_text("not an Excel workbook", encoding="utf-8")

    exit_code = main(
        ["validate", str(broken), str(valid), "--schema", str(schema), "--output", str(output_directory)]
    )

    assert exit_code == 1
    broken_report = json.loads((output_directory / "broken.validation.json").read_text(encoding="utf-8"))
    valid_report = json.loads((output_directory / "valid.validation.json").read_text(encoding="utf-8"))
    assert broken_report["issues"][0]["code"] == "unreadable_workbook"
    assert valid_report["status"] == "passed"
