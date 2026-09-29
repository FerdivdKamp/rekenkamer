import json
from pathlib import Path

import pandas as pd


def load_schema(schema_file: Path) -> dict:
    """Load the reference schema from JSON."""
    with open(schema_file, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_excel_file(
    file_path: Path,
    expected_schema: dict
) -> dict:
    """
    Validate one Excel workbook against the expected schema.

    Returns one result dictionary suitable for writing to CSV.
    """
    result = {
        "file": file_path.name,
        "status": "OK",
        "issues": ""
    }

    issues = []

    try:
        workbook = pd.read_excel(file_path, sheet_name=None)
    except Exception as error:
        result["status"] = "ERROR"
        result["issues"] = f"Could not read workbook: {error}"
        return result

    # Compare sheets
    expected_sheets = set(expected_schema.keys())
    actual_sheets = set(workbook.keys())

    missing_sheets = expected_sheets - actual_sheets
    extra_sheets = actual_sheets - expected_sheets

    if missing_sheets:
        issues.append(
            f"Missing sheets: {sorted(missing_sheets)}"
        )

    if extra_sheets:
        issues.append(
            f"Unexpected sheets: {sorted(extra_sheets)}"
        )

    # Compare each expected sheet
    for sheet_name in expected_sheets & actual_sheets:
        df = workbook[sheet_name]
        sheet_schema = expected_schema[sheet_name]

        expected_columns = sheet_schema["columns"]
        actual_columns = {
            str(column): str(df[column].dtype)
            for column in df.columns
        }

        # Check columns
        expected_column_names = set(expected_columns.keys())
        actual_column_names = set(actual_columns.keys())

        missing_columns = expected_column_names - actual_column_names
        extra_columns = actual_column_names - expected_column_names

        if missing_columns:
            issues.append(
                f"{sheet_name}: missing columns "
                f"{sorted(missing_columns)}"
            )

        if extra_columns:
            issues.append(
                f"{sheet_name}: unexpected columns "
                f"{sorted(extra_columns)}"
            )

        # Check datatypes for columns that exist in both
        common_columns = expected_column_names & actual_column_names

        for column in common_columns:
            expected_dtype = expected_columns[column]
            actual_dtype = actual_columns[column]

            if expected_dtype != actual_dtype:
                issues.append(
                    f"{sheet_name}.{column}: "
                    f"dtype expected {expected_dtype}, "
                    f"found {actual_dtype}"
                )

    if issues:
        result["status"] = "ERROR"
        result["issues"] = " | ".join(issues)

    return result


def validate_excel_files(
    files: list[Path],
    schema_file: Path,
    output_csv: Path
) -> pd.DataFrame:
    """
    Validate multiple Excel files and write the results to CSV.
    """
    expected_schema = load_schema(schema_file)

    results = []

    for file_path in files:
        result = validate_excel_file(
            file_path,
            expected_schema
        )
        results.append(result)

    results_df = pd.DataFrame(results)

    results_df.to_csv(
        output_csv,
        index=False
    )

    return results_df