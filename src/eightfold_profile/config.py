"""Runtime JSON configuration loader and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from eightfold_profile.models import DEFAULT_OUTPUT_FIELDS


class MissingValueBehavior(str, Enum):
    NULL = "null"
    OMIT = "omit"
    ERROR = "error"


DEFAULT_OUTPUT_FIELDS = list(DEFAULT_OUTPUT_FIELDS)


@dataclass
class AppConfig:
    """Controls projection, metadata, and missing-value handling."""

    output_fields: list[str] = field(default_factory=lambda: list(DEFAULT_OUTPUT_FIELDS))
    field_mapping: dict[str, str] = field(default_factory=dict)
    include_confidence: bool = True
    include_provenance: bool = True
    missing_value_behavior: MissingValueBehavior = MissingValueBehavior.NULL
    default_country_code: str = "US"
    skills_synonyms: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AppConfig:
        if not data:
            return cls()
        behavior = data.get("missing_value_behavior", "null")
        try:
            missing = MissingValueBehavior(behavior)
        except ValueError as exc:
            raise ValueError(
                f"invalid missing_value_behavior: {behavior!r}; "
                "expected one of: null, omit, error"
            ) from exc
        return cls(
            output_fields=list(data.get("output_fields", DEFAULT_OUTPUT_FIELDS)),
            field_mapping=dict(data.get("field_mapping", {})),
            include_confidence=bool(data.get("include_confidence", True)),
            include_provenance=bool(data.get("include_provenance", True)),
            missing_value_behavior=missing,
            default_country_code=str(data.get("default_country_code", "US")),
            skills_synonyms=dict(data.get("skills_synonyms", {})),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> AppConfig:
        config_path = Path(path)
        if not config_path.is_file():
            raise FileNotFoundError(f"config file not found: {config_path}")
        try:
            with config_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in config file {config_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("config root must be a JSON object")
        return cls.from_dict(data)

    def canonical_output_fields(self) -> list[str]:
        """Fields requested before metadata toggles are applied."""
        fields = list(self.output_fields)
        if self.include_provenance and "provenance" not in fields:
            fields.append("provenance")
        if self.include_confidence and "overall_confidence" not in fields:
            fields.append("overall_confidence")
        return fields


def load_config(path: str | Path | None) -> AppConfig:
    """Load config from path or return defaults."""
    if path is None:
        return AppConfig()
    return AppConfig.from_json_file(path)
