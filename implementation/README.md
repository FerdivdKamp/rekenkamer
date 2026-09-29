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
```

## Run the tests

With the virtual environment activated, run the complete test suite from the
`implementation` directory:

```powershell
pytest
```

To see each test name and its result, use `pytest -v`. To run only the upload
API tests while working on that area, use:

```powershell
pytest tests\test_api.py
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

## Run the upload API

The development API accepts one `.xlsx` multipart upload at `POST /uploads` and
validates it synchronously. It stores raw workbook bytes under `uploads/raw/`
by SHA-256 checksum, so identical re-uploads reuse the original immutable raw
file. Each upload still receives its own ID, validation report, and row in the
persistent SQLite metadata database (`uploads/metadata/uploads.sqlite3` by
default). Metadata includes the original filename, optional
`source_organisation` multipart field, checksum, schema version, timestamps,
validation status, and raw/report locations. Set `REKENKAMER_METADATA_DIRECTORY`
to store that database elsewhere.

First complete [Setup](#setup) in this `implementation` directory. In every
new PowerShell session, activate the project's virtual environment before
starting the server:

```powershell
.\.venv\Scripts\Activate.ps1
```

Set `REKENKAMER_SCHEMA_PATH` to the validation schema to use. The packaged
development schema is deliberately empty, so configure a service schema before
using the API for meaningful validation. `REKENKAMER_UPLOAD_DIRECTORY` and
`REKENKAMER_MAX_UPLOAD_BYTES` (default: `10485760`) are optional.

```powershell
$env:REKENKAMER_SCHEMA_PATH = ".\schema.json"
python -m uvicorn rekenkamer_pipeline.api:app --reload
```

`python -m uvicorn` runs the local ASGI web server from the active virtual
environment: it imports the FastAPI application
(`rekenkamer_pipeline.api:app`) and makes it available at
http://127.0.0.1:8000 (note that this page says nothing, use one of the endpoints below instead). 
The `--reload` option is intended for development; it restarts the server after a source-code change. 
Leave this terminal running while using the API, and stop it with `Ctrl+C`.

FastAPI supplies an interactive Swagger UI. Open http://127.0.0.1:8000/docs in
a browser, expand `POST /uploads`, select **Try it out**, choose an `.xlsx`
file, and click **Execute**. The same page also lets you call `GET /health`.
The alternative OpenAPI documentation UI is at http://127.0.0.1:8000/redoc.

A successful upload returns `201 Created` with `upload_id` and `report`; a
structurally invalid or unreadable workbook still returns `201` with a failed
validation report. Missing files, non-`.xlsx` files, and uploads larger than
the configured limit return `4xx`.

### Inspect persisted uploads

After testing an upload, inspect the metadata database from the
`implementation` directory. Python includes SQLite support, so this does not
require installing a separate database client:

```powershell
python
```

```python
import sqlite3

connection = sqlite3.connect("uploads/metadata/uploads.sqlite3")
connection.row_factory = sqlite3.Row

for row in connection.execute("""
    SELECT upload_id, original_filename, validation_status, received_at,
           raw_file_location, report_location
    FROM uploads
    ORDER BY received_at DESC
"""):
    print(dict(row))

connection.close()
```

The `raw_file_location` and `report_location` values point to the stored
workbook and its JSON validation report, respectively. If the optional
`sqlite3` command-line tool is installed, the equivalent query is:

```powershell
sqlite3 .\uploads\metadata\uploads.sqlite3 "SELECT upload_id, original_filename, validation_status, received_at FROM uploads ORDER BY received_at DESC;"
```
