"""Structural validation of Excel workbooks against JSON schemas."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api import types as pandas_types


class SchemaError(ValueError):
    """Raised when a validation schema cannot be interpreted."""


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _normalise_columns(columns: Any, sheet_name: str) -> dict[str, str]:
    if isinstance(columns, Mapping):
        result = {
            str(name): str(definition.get("type", "any"))
            if isinstance(definition, Mapping)
            else str(definition)
            for name, definition in columns.items()
        }
    elif isinstance(columns, list):
        result = {}
        for definition in columns:
            if not isinstance(definition, Mapping) or "name" not in definition:
                raise SchemaError(f"Sheet '{sheet_name}' has a column without a name.")
            result[str(definition["name"])] = str(definition.get("type", "any"))
    else:
        raise SchemaError(f"Sheet '{sheet_name}' must define columns as an object or list.")
    return result


def _normalise_sheets(schema: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    sheets = schema.get("sheets")
    if isinstance(sheets, Mapping):
        result = {}
        for name, definition in sheets.items():
            if not isinstance(definition, Mapping):
                raise SchemaError(f"Sheet '{name}' definition must be an object.")
            result[str(name)] = _normalise_columns(definition.get("columns"), str(name))
        return result
    if isinstance(sheets, list):
        result = {}
        for definition in sheets:
            if not isinstance(definition, Mapping) or "name" not in definition:
                raise SchemaError("Each sheet definition must contain a name.")
            name = str(definition["name"])
            result[name] = _normalise_columns(definition.get("columns"), name)
        return result
    raise SchemaError("Schema must contain a 'sheets' object or list.")


def load_schema(schema_path: Path) -> tuple[dict[str, dict[str, str]], str]:
    """Load a JSON schema and return its sheets and report identifier."""
    try:
        contents = schema_path.read_bytes()
        schema = json.loads(contents)
    except FileNotFoundError as error:
        raise SchemaError(f"Schema file does not exist: {schema_path}") from error
    except json.JSONDecodeError as error:
        raise SchemaError(f"Schema file is not valid JSON: {schema_path}") from error
    if not isinstance(schema, Mapping):
        raise SchemaError("Schema root must be a JSON object.")
    identifier = str(schema.get("version") or schema.get("schema_version") or "")
    if not identifier:
        identifier = f"sha256:{hashlib.sha256(contents).hexdigest()}"
    return _normalise_sheets(schema), identifier


def _actual_type(series: pd.Series) -> str:
    """Return the structural type inferred by pandas for one Excel column."""
    non_empty = series.dropna()
    if non_empty.empty:
        return "empty"
    dtype = non_empty.dtype
    if pandas_types.is_bool_dtype(dtype):
        return "boolean"
    if pandas_types.is_integer_dtype(dtype):
        return "integer"
    if pandas_types.is_numeric_dtype(dtype):
        return "number"
    if pandas_types.is_datetime64_any_dtype(dtype):
        return "date"
    return "string"


def _type_matches(expected: str, actual: str) -> bool:
    expected = expected.strip().lower()
    aliases = {"str": "string", "text": "string", "float": "number", "int": "integer", "bool": "boolean", "datetime": "date"}
    expected = aliases.get(expected, expected)
    return expected in {"", "any", "object"} or expected == actual or (
        expected == "number" and actual == "integer"
    ) or actual == "empty"


def validate_workbook(workbook_path: Path, schema_path: Path) -> dict[str, Any]:
    """Validate one workbook and return a JSON-serialisable report."""
    sheets, schema_identifier = load_schema(schema_path)
    report: dict[str, Any] = {
        "source_filename": workbook_path.name,
        "status": "passed",
        "issues": [],
        "timestamp": datetime.now(UTC).isoformat(),
        "schema_version": schema_identifier,
    }
    issues: list[dict[str, Any]] = report["issues"]
    try:
        excel = pd.ExcelFile(workbook_path)
    except Exception as error:  # noqa: BLE001 - pandas has several reader-specific exceptions
        issues.append(_issue("unreadable_workbook", f"Could not read workbook: {error}"))
        report["status"] = "failed"
        return report

    actual_sheets = set(excel.sheet_names)
    expected_sheets = set(sheets)
    for name in sorted(expected_sheets - actual_sheets):
        issues.append(_issue("missing_sheet", f"Missing expected sheet '{name}'.", sheet=name))
    for name in sorted(actual_sheets - expected_sheets):
        issues.append(_issue("unexpected_sheet", f"Unexpected sheet '{name}'.", sheet=name))

    for name in sorted(expected_sheets & actual_sheets):
        try:
            frame = pd.read_excel(excel, sheet_name=name)
        except Exception as error:  # noqa: BLE001 - pandas has several reader-specific exceptions
            issues.append(_issue("unreadable_sheet", f"Could not read sheet '{name}': {error}", sheet=name))
            continue
        expected_columns = sheets[name]
        actual_columns = {str(column) for column in frame.columns}
        for column in sorted(set(expected_columns) - actual_columns):
            issues.append(_issue("missing_column", f"Missing expected column '{column}'.", sheet=name, column=column))
        for column in sorted(actual_columns - set(expected_columns)):
            issues.append(_issue("unexpected_column", f"Unexpected column '{column}'.", sheet=name, column=column))
        for column in sorted(set(expected_columns) & actual_columns):
            actual = _actual_type(frame[column])
            expected = expected_columns[column]
            if not _type_matches(expected, actual):
                issues.append(
                    _issue(
                        "column_type_mismatch",
                        f"Column '{column}' is {actual}; expected {expected}.",
                        sheet=name,
                        column=column,
                        expected_type=expected,
                        actual_type=actual,
                    )
                )
    if issues:
        report["status"] = "failed"
    return report


def validate_workbooks(workbook_paths: Iterable[Path], schema_path: Path) -> list[dict[str, Any]]:
    """Validate every supplied workbook, retaining reports after failures."""
    # Parse first so a malformed schema does not create misleading per-file reports.
    load_schema(schema_path)
    return [validate_workbook(Path(workbook), schema_path) for workbook in workbook_paths]


def write_reports(reports: list[dict[str, Any]], output_path: Path) -> list[Path]:
    """Write reports atomically enough for command-line use and return their paths."""
    if output_path.suffix:
        if len(reports) != 1:
            raise ValueError("For multiple workbooks, --output must be a directory path.")
        destinations = [output_path]
    else:
        output_path.mkdir(parents=True, exist_ok=True)
        destinations = [output_path / f"{Path(report['source_filename']).stem}.validation.json" for report in reports]
    for destination, report in zip(destinations, reports, strict=True):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destinations
