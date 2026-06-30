"""Config-driven output projection and field remapping."""

from __future__ import annotations

from typing import Any

from eightfold_profile.config import AppConfig, MissingValueBehavior
from eightfold_profile.projection.provenance_projection import project_provenance

METADATA_FIELDS = {
    "overall_confidence": "include_confidence",
    "provenance": "include_provenance",
}


class ProjectionError(ValueError):
    """Raised when required fields are missing and config demands an error."""


_OMIT = object()


def _handle_missing(field_name: str, config: AppConfig) -> Any:
    if config.missing_value_behavior == MissingValueBehavior.ERROR:
        raise ProjectionError(f"missing required field: {field_name}")
    if config.missing_value_behavior == MissingValueBehavior.OMIT:
        return _OMIT
    return None


def _has_field(canonical: dict[str, Any], field_name: str) -> bool:
    if field_name not in canonical:
        return False
    value = canonical[field_name]
    if value is None:
        return False
    if isinstance(value, list):
        return True
    if isinstance(value, dict) and not value:
        return False
    return True


def _effective_output_fields(config: AppConfig) -> list[str]:
    """Drop metadata fields from projection when disabled by runtime config."""
    fields: list[str] = []
    for name in config.output_fields:
        flag = METADATA_FIELDS.get(name)
        if flag == "include_confidence" and not config.include_confidence:
            continue
        if flag == "include_provenance" and not config.include_provenance:
            continue
        fields.append(name)
    return fields


def _strip_disabled_metadata(output: dict[str, Any], config: AppConfig) -> None:
    """Ensure confidence/provenance metadata never leak when toggled off."""
    if not config.include_confidence:
        output.pop("overall_confidence", None)
    if not config.include_provenance:
        output.pop("provenance", None)


def project_profile(canonical: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    """Project canonical profile to output JSON according to runtime config."""
    output: dict[str, Any] = {}

    for output_name in _effective_output_fields(config):
        source_name = config.field_mapping.get(output_name, output_name)
        if not _has_field(canonical, source_name):
            missing = _handle_missing(source_name, config)
            if missing is _OMIT:
                continue
            output[output_name] = missing
            continue
        output[output_name] = canonical[source_name]

    if config.include_provenance and "provenance" in canonical:
        if "provenance" in _effective_output_fields(config):
            output["provenance"] = project_provenance(canonical["provenance"], output)

    _strip_disabled_metadata(output, config)
    return output
