"""Build the assignment canonical profile from merged data."""

from __future__ import annotations

from typing import Any

from eightfold_profile.config import AppConfig
from eightfold_profile.merging.merger import MergedProfile
from eightfold_profile.models import Provenance, SkillValue


def _overall_confidence(merged: MergedProfile) -> float:
    scores: list[float] = []
    scores.extend(field.confidence for field in merged.scalars.values())
    if merged.location:
        scores.append(merged.location.confidence)
    scores.extend(item.confidence for item in merged.emails)
    scores.extend(item.confidence for item in merged.phones)
    scores.extend(skill.confidence for skill in merged.skills)
    if merged.experience:
        scores.append(merged.experience.confidence)
    if merged.education:
        scores.append(merged.education.confidence)
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def _scalar(merged: MergedProfile, name: str) -> Any:
    field = merged.scalars.get(name)
    return field.value if field is not None else None


def _public_location(location: dict[str, str]) -> dict[str, str]:
    return {
        key: location[key]
        for key in ("city", "region", "country")
        if key in location and location[key]
    }


def _build_links(merged: MergedProfile) -> dict[str, Any]:
    return {
        "linkedin": _scalar(merged, "linkedin_url"),
        "github": _scalar(merged, "github_url"),
        "portfolio": None,
        "other": [],
    }


def _build_headline(merged: MergedProfile) -> str | None:
    return _scalar(merged, "summary") or _scalar(merged, "current_title")


def _build_years_experience(merged: MergedProfile) -> float | None:
    value = _scalar(merged, "total_years_experience")
    if value is None:
        return None
    return float(value)


def _serialize_skills(skills: list[SkillValue]) -> list[dict[str, Any]]:
    return [
        {
            "name": skill.name,
            "confidence": round(skill.confidence, 4),
            "sources": [source.value for source in skill.sources],
        }
        for skill in skills
    ]


def _provenance_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return record["field"], record["source"], record["method"]


def _dedupe_provenance(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate provenance rows that share field, source, and method."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        key = _provenance_key(record)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _collect_provenance(merged: MergedProfile) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def add(field: str, provenance: list[Provenance]) -> None:
        for item in provenance:
            records.append(
                {
                    "field": field if item.field_path == field else item.field_path,
                    "source": item.source.value,
                    "method": item.extractor,
                }
            )

    for name, field in merged.scalars.items():
        add(name, field.provenance)

    if merged.location:
        add("location", merged.location.provenance)

    for index, email in enumerate(merged.emails):
        add(f"emails[{index}]", email.provenance)

    for index, phone in enumerate(merged.phones):
        add(f"phones[{index}]", phone.provenance)

    for index, skill in enumerate(merged.skills):
        add(f"skills[{index}].name", skill.provenance)

    if merged.experience:
        add("experience", merged.experience.provenance)

    if merged.education:
        add("education", merged.education.provenance)

    for link_name, scalar_name in (("linkedin", "linkedin_url"), ("github", "github_url")):
        link_field = merged.scalars.get(scalar_name)
        if link_field and link_field.value:
            add(f"links.{link_name}", link_field.provenance)

    return _dedupe_provenance(records)


def build_canonical_profile(merged: MergedProfile, config: AppConfig) -> dict[str, Any]:
    """Assemble the assignment default output schema."""
    profile: dict[str, Any] = {
        "candidate_id": _scalar(merged, "candidate_id"),
        "full_name": _scalar(merged, "full_name"),
        "emails": [item.value for item in merged.emails],
        "phones": [item.value for item in merged.phones],
        "location": _public_location(merged.location.value) if merged.location else None,
        "links": _build_links(merged),
        "headline": _build_headline(merged),
        "years_experience": _build_years_experience(merged),
        "skills": _serialize_skills(merged.skills),
        "experience": merged.experience.value if merged.experience else [],
        "education": merged.education.value if merged.education else [],
    }

    if config.include_provenance:
        profile["provenance"] = _collect_provenance(merged)

    if config.include_confidence:
        profile["overall_confidence"] = _overall_confidence(merged)

    return profile
