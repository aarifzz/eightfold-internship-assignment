"""Structured recruiter CSV parsing."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from eightfold_profile.confidence.scorer import Scorer
from eightfold_profile.models import FieldValue, ParsedProfile, Provenance, SourceType


class CSVParseError(ValueError):
    """Raised when recruiter CSV cannot be parsed."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field(
    name: str,
    raw: Any,
    *,
    confidence: float,
    extractor: str,
) -> FieldValue | None:
    cleaned = _clean(raw)
    if cleaned is None:
        return None
    return FieldValue(
        value=cleaned,
        confidence=confidence,
        provenance=[
            Provenance(
                source=SourceType.RECRUITER_CSV,
                raw_value=raw,
                extractor=extractor,
                field_path=name,
            )
        ],
    )


def _contact_field(
    name: str,
    raw: Any,
    *,
    confidence: float,
    index: int,
) -> FieldValue | None:
    cleaned = _clean(raw)
    if cleaned is None:
        return None
    return FieldValue(
        value=cleaned,
        confidence=confidence,
        provenance=[
            Provenance(
                source=SourceType.RECRUITER_CSV,
                raw_value=raw,
                extractor="csv_parser.parse_recruiter_csv",
                field_path=f"{name}[{index}]",
            )
        ],
    )


def _split_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[;,|]", raw)
    return [part.strip() for part in parts if part.strip()]


def parse_recruiter_csv(path: str | Path, *, candidate_id: str | None = None) -> ParsedProfile:
    """
    Parse recruiter CSV into a partial profile.

    Assumptions:
      - First data row is used when candidate_id is omitted.
      - When candidate_id is provided, the matching row is selected.
      - Column names are case-insensitive and accept common aliases.
    """
    csv_path = Path(path)
    if not csv_path.is_file():
        raise CSVParseError(f"CSV file not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise CSVParseError("CSV has no header row")
        rows = list(reader)

    if not rows:
        raise CSVParseError("CSV contains no data rows")

    normalized_rows = [{k.strip().lower(): v for k, v in row.items() if k} for row in rows]

    selected = normalized_rows[0]
    if candidate_id is not None:
        matches = [
            row
            for row in normalized_rows
            if _clean(row.get("candidate_id")) == candidate_id
        ]
        if not matches:
            raise CSVParseError(f"candidate_id {candidate_id!r} not found in CSV")
        selected = matches[0]

    profile = ParsedProfile(source=SourceType.RECRUITER_CSV)
    scorer = Scorer()

    alias_map = {
        "candidate_id": ("candidate_id", "id"),
        "first_name": ("first_name", "firstname", "given_name"),
        "last_name": ("last_name", "lastname", "family_name", "surname"),
        "email": ("email", "email_address"),
        "emails": ("emails", "email_list"),
        "phone": ("phone", "phone_number", "mobile"),
        "phones": ("phones", "phone_list"),
        "location": ("location", "city", "address"),
        "current_title": ("current_title", "title", "job_title"),
        "current_company": ("current_company", "company", "employer"),
        "linkedin_url": ("linkedin_url", "linkedin"),
        "github_url": ("github_url", "github"),
        "total_years_experience": ("total_years_experience", "years_experience", "experience_years"),
        "summary": ("summary", "notes", "recruiter_notes"),
        "skills": ("skills", "skill_list"),
    }

    def pick(*keys: str) -> Any:
        for key in keys:
            if key in selected and _clean(selected[key]) is not None:
                return selected[key]
        return None

    for canonical, aliases in alias_map.items():
        if canonical == "skills":
            profile.skills = _split_list(_clean(pick(*aliases)) or "")
            profile.skill_confidence = scorer.csv_skills_confidence(bool(profile.skills))
            continue
        if canonical in {"email", "emails"}:
            continue
        if canonical in {"phone", "phones"}:
            continue
        raw = pick(*aliases)
        field_value = _field(
            canonical,
            raw,
            confidence=scorer.csv_scalar_confidence(canonical, raw),
            extractor="csv_parser.parse_recruiter_csv",
        )
        if field_value is not None:
            profile.fields[canonical] = field_value

    email_values = _split_list(_clean(pick("emails", "email_list")) or "") or (
        [_clean(pick("email", "email_address"))] if _clean(pick("email", "email_address")) else []
    )
    phone_values = _split_list(_clean(pick("phones", "phone_list")) or "") or (
        [_clean(pick("phone", "phone_number", "mobile"))] if _clean(pick("phone", "phone_number", "mobile")) else []
    )

    profile.emails = [
        item
        for i, raw in enumerate(email_values)
        if (item := _contact_field("emails", raw, confidence=scorer.csv_scalar_confidence("email", raw), index=i))
    ]
    profile.phones = [
        item
        for i, raw in enumerate(phone_values)
        if (item := _contact_field("phones", raw, confidence=scorer.csv_scalar_confidence("phone", raw), index=i))
    ]

    first = profile.fields.get("first_name")
    last = profile.fields.get("last_name")
    if first and last:
        profile.fields["full_name"] = FieldValue(
            value=f"{first.value} {last.value}".strip(),
            confidence=min(first.confidence, last.confidence),
            provenance=first.provenance + last.provenance,
        )
    elif first:
        profile.fields["full_name"] = first
    elif last:
        profile.fields["full_name"] = last

    return profile
