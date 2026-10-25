"""Approved, versioned workbook schemas and source-type defaults."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .validation import SchemaError, validate_schema_definition


class SchemaRegistryError(ValueError):
    """Raised when a registry or schema selection is invalid."""


@dataclass(frozen=True)
class RegisteredSchema:
    """One approved immutable schema version."""

    schema_id: str
    version: str
    effective_from: str
    effective_to: str | None
    owner: str
    definition: dict[str, Any]

    def public_data(self, *, include_definition: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.schema_id,
            "version": self.version,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "owner": self.owner,
        }
        if include_definition:
            result["definition"] = self.definition
        return result


class SchemaRegistry:
    """Read-only registry loaded and validated before it is used by the API."""

    def __init__(
        self, schemas: list[RegisteredSchema], defaults: dict[str, tuple[str, str]]
    ) -> None:
        self._schemas = {(schema.schema_id, schema.version): schema for schema in schemas}
        self._defaults = defaults

    @classmethod
    def from_path(cls, path: Path) -> SchemaRegistry:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise SchemaRegistryError(f"Schema registry does not exist: {path}") from error
        except json.JSONDecodeError as error:
            raise SchemaRegistryError(f"Schema registry is not valid JSON: {path}") from error
        if not isinstance(raw, Mapping) or not isinstance(raw.get("schemas"), list):
            raise SchemaRegistryError("Schema registry must contain a 'schemas' list.")

        schemas: list[RegisteredSchema] = []
        seen: set[tuple[str, str]] = set()
        for entry in raw["schemas"]:
            if not isinstance(entry, Mapping):
                raise SchemaRegistryError("Each registered schema must be an object.")
            schema_id = _required_text(entry, "id")
            version = _required_text(entry, "version")
            effective_from = _required_date(entry, "effective_from")
            effective_to = _optional_date(entry, "effective_to")
            owner = _required_text(entry, "owner")
            if effective_to and effective_to < effective_from:
                raise SchemaRegistryError("Schema effective_to must not precede effective_from.")
            definition = entry.get("definition")
            if not isinstance(definition, Mapping):
                raise SchemaRegistryError(
                    f"Schema '{schema_id}' version '{version}' needs a definition."
                )
            try:
                validate_schema_definition(definition)
            except SchemaError as error:
                raise SchemaRegistryError(
                    f"Schema '{schema_id}' version '{version}' has an invalid definition: {error}"
                ) from error
            key = (schema_id, version)
            if key in seen:
                raise SchemaRegistryError(
                    f"Schema '{schema_id}' version '{version}' is registered twice."
                )
            seen.add(key)
            schemas.append(
                RegisteredSchema(
                    schema_id, version, effective_from, effective_to, owner, dict(definition)
                )
            )

        defaults_raw = raw.get("defaults")
        if not isinstance(defaults_raw, Mapping):
            raise SchemaRegistryError("Schema registry must contain a 'defaults' object.")
        defaults: dict[str, tuple[str, str]] = {}
        for source_type, selection in defaults_raw.items():
            if (
                not isinstance(source_type, str)
                or not source_type.strip()
                or not isinstance(selection, Mapping)
            ):
                raise SchemaRegistryError("Each source-type default must be a schema selection.")
            schema_id = _required_text(selection, "id")
            version = _required_text(selection, "version")
            if (schema_id, version) not in seen:
                raise SchemaRegistryError(
                    f"Default for source type '{source_type}' refers to an unknown schema version."
                )
            defaults[source_type] = (schema_id, version)
        return cls(schemas, defaults)

    def list(self) -> list[dict[str, Any]]:
        schemas = sorted(self._schemas.values(), key=lambda schema: (schema.schema_id, schema.version))
        return [schema.public_data() for schema in schemas]

    def get(self, schema_id: str, version: str) -> RegisteredSchema:
        try:
            return self._schemas[(schema_id, version)]
        except KeyError as error:
            raise SchemaRegistryError(
                f"Unknown schema '{schema_id}' version '{version}'."
            ) from error

    def select(
        self, source_type: str, schema_id: str | None, version: str | None
    ) -> RegisteredSchema:
        if bool(schema_id) != bool(version):
            raise SchemaRegistryError("schema_id and schema_version must be supplied together.")
        if schema_id and version:
            return self.get(schema_id, version)
        try:
            default_id, default_version = self._defaults[source_type]
        except KeyError as error:
            raise SchemaRegistryError(
                f"No default schema is configured for source type '{source_type}'."
            ) from error
        return self.get(default_id, default_version)


def _required_text(entry: Mapping[str, Any], name: str) -> str:
    value = entry.get(name)
    if not isinstance(value, str) or not value.strip():
        raise SchemaRegistryError(f"Schema registry field '{name}' must be a non-empty string.")
    return value


def _required_date(entry: Mapping[str, Any], name: str) -> str:
    value = _required_text(entry, name)
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise SchemaRegistryError(f"Schema registry field '{name}' must be an ISO date.") from error
    return value


def _optional_date(entry: Mapping[str, Any], name: str) -> str | None:
    value = entry.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaRegistryError(f"Schema registry field '{name}' must be an ISO date or null.")
    return _required_date(entry, name)
