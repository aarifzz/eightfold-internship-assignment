"""JSON Schema validation for projected candidate profiles."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from eightfold_profile.config import AppConfig

SCHEMA_PATH = Path(__file__).with_name("candidate_schema.json")


def load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def schema_for_config(config: AppConfig, *, base_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Derive a JSON Schema that matches the projected output shape for this config.

    When confidence or provenance are disabled, related top-level properties are
    removed so validation does not expect intentionally omitted metadata.
    """
    schema = copy.deepcopy(base_schema or load_schema())
    properties = schema["properties"]

    if not config.include_confidence:
        properties.pop("overall_confidence", None)

    if not config.include_provenance:
        properties.pop("provenance", None)

    return schema


def validate_output(
    payload: dict[str, Any],
    *,
    config: AppConfig | None = None,
    schema: dict[str, Any] | None = None,
) -> None:
    """
    Validate projected output against the canonical schema.

    When `config` is provided, the schema is tailored to `include_confidence` and
    `include_provenance` so intentionally omitted metadata is not required.
    """
    if schema is not None:
        active_schema = schema
    elif config is not None:
        active_schema = schema_for_config(config)
    else:
        active_schema = load_schema()

    validator = Draft202012Validator(active_schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if errors:
        messages = "; ".join(f"{'.'.join(map(str, error.path))}: {error.message}" for error in errors)
        raise ValidationError(f"output validation failed: {messages}")
