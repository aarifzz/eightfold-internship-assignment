"""Remap canonical provenance to the projected output schema."""

from __future__ import annotations

from typing import Any

# Internal merge/builder field paths -> assignment output field paths.
INTERNAL_FIELD_MAP: dict[str, str] = {
    "first_name": "full_name",
    "last_name": "full_name",
    "summary": "headline",
    "current_title": "headline",
    "total_years_experience": "years_experience",
    "linkedin_url": "links.linkedin",
    "github_url": "links.github",
}

# Internal-only fields with no representation in the output schema.
INTERNAL_ONLY_FIELDS = frozenset(
    {
        "current_company",
    }
)


def _dedupe_provenance(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        key = (record["field"], record["source"], record["method"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _map_provenance_field(field: str) -> str | None:
    if field in INTERNAL_ONLY_FIELDS:
        return None
    return INTERNAL_FIELD_MAP.get(field, field)


def _output_field_paths(output: dict[str, Any]) -> set[str]:
    """Field paths that exist in the projected output payload."""
    paths: set[str] = set()

    for key, value in output.items():
        if key == "emails" and isinstance(value, list):
            paths.update(f"emails[{index}]" for index in range(len(value)))
            continue
        if key == "phones" and isinstance(value, list):
            paths.update(f"phones[{index}]" for index in range(len(value)))
            continue
        if key == "skills" and isinstance(value, list):
            paths.update(f"skills[{index}].name" for index in range(len(value)))
            continue
        if key == "links" and isinstance(value, dict):
            for link_key in ("linkedin", "github", "portfolio"):
                if value.get(link_key):
                    paths.add(f"links.{link_key}")
            continue
        if value is not None:
            paths.add(key)

    return paths


def project_provenance(
    canonical_provenance: list[dict[str, Any]],
    output: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Filter and remap provenance so it only references projected output fields.

    Derived output fields (e.g. full_name, headline) aggregate provenance from
    all contributing internal source fields.
    """
    allowed = _output_field_paths(output)
    projected: list[dict[str, Any]] = []

    for record in canonical_provenance:
        mapped_field = _map_provenance_field(record["field"])
        if mapped_field is None or mapped_field not in allowed:
            continue
        projected.append(
            {
                "field": mapped_field,
                "source": record["source"],
                "method": record["method"],
            }
        )

    return _dedupe_provenance(projected)
