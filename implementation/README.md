# Implementation

This workspace contains the production Python package for ingestion and
data-quality checks. The `src/` layout keeps application code separate from
tests and packaging metadata.

## Setup

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
```

## Validate workbooks

Create a JSON schema describing the sheets and columns expected in a workbook:

```json
{
  "version": "2026-09",
  "sheets": {
    "Overzicht": {
      "columns": {
        "Ministerie": "string",
        "Bedrag": "number",
        "Peildatum": "date"
      }
    }
  }
}
```

Validate one workbook and write its JSON report. A `--output` value with a file
suffix writes that exact file; a suffix-less value is treated as a directory:

```powershell
rekenkamer-pipeline validate .\data\input.xlsx --schema .\schema.json --output .\report.json

# Also writes .\reports\input.validation.json
rekenkamer-pipeline validate .\data\input.xlsx --schema .\schema.json --output .\reports
```

The command exits with `0` when validation passes and `1` when any structural
issue is found. Reports contain the source filename, status, all issues, a UTC
timestamp, and the schema version (or a SHA-256 checksum when no version is
provided). Structural checks cover unreadable workbooks, unexpected or missing
sheets and columns, and inferred column-type mismatches. Empty columns do not
produce a type mismatch.

Several workbooks can be validated in one command. Use a directory for output;
one report is written per workbook even if another workbook fails:

```powershell
rekenkamer-pipeline validate .\data\one.xlsx .\data\two.xlsx --schema .\schema.json --output .\reports
```
