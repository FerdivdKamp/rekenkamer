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

Run the placeholder command with:

```powershell
rekenkamer-pipeline
```
