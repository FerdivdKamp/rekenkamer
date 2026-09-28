"""Command-line interface for the data pipeline."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .validation import SchemaError, validate_workbooks, write_reports


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(prog="rekenkamer-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate Excel workbooks against a JSON schema")
    validate.add_argument("workbooks", nargs="+", type=Path, help="workbook(s) to validate")
    validate.add_argument("--schema", required=True, type=Path, help="path to the JSON schema")
    validate.add_argument(
        "--output",
        required=True,
        type=Path,
        help="report file for one workbook, or report directory for multiple workbooks",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a pipeline command and return its process exit status."""
    args = build_parser().parse_args(argv)
    if args.command != "validate":  # pragma: no cover - argparse guards this
        return 2

    try:
        reports = validate_workbooks(args.workbooks, args.schema)
        paths = write_reports(reports, args.output)
    except (OSError, SchemaError, ValueError) as error:
        print(f"Error: {error}")
        return 2

    for path, report in zip(paths, reports, strict=True):
        print(f"{report['status']}: {report['source_filename']} -> {path}")
    return 0 if all(report["status"] == "passed" for report in reports) else 1
