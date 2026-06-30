"""Normalization orchestration for parsed profiles."""

from __future__ import annotations

from eightfold_profile.config import AppConfig
from eightfold_profile.models import EducationEntry, ExperienceEntry, FieldValue, ParsedProfile
from eightfold_profile.normalization.dates import normalize_date
from eightfold_profile.normalization.email import normalize_email
from eightfold_profile.normalization.location import normalize_location
from eightfold_profile.normalization.phone import normalize_phone
from eightfold_profile.normalization.skills import canonicalize_skills


class NormalizationError(ValueError):
    """Raised when a value cannot be normalized."""


def _normalize_scalar(field_name: str, field: FieldValue, config: AppConfig) -> FieldValue:
    raw = str(field.value)
    try:
        if field_name == "total_years_experience":
            normalized = float(raw)
            if normalized < 0:
                raise ValueError("years of experience cannot be negative")
        elif field_name == "location":
            normalized = normalize_location(raw, default_country=config.default_country_code)
            if normalized is None:
                raise ValueError("location could not be parsed")
        else:
            normalized = raw.strip()
    except ValueError as exc:
        raise NormalizationError(f"failed to normalize {field_name}: {exc}") from exc

    return FieldValue(value=normalized, confidence=field.confidence, provenance=list(field.provenance))


def _normalize_contact_list(
    items: list[FieldValue],
    *,
    normalizer,
    config: AppConfig,
) -> list[FieldValue]:
    normalized: list[FieldValue] = []
    for item in items:
        try:
            value = normalizer(str(item.value), default_region=config.default_country_code)
        except TypeError:
            value = normalizer(str(item.value))
        except ValueError as exc:
            raise NormalizationError(f"failed to normalize contact value: {exc}") from exc
        normalized.append(
            FieldValue(value=value, confidence=item.confidence, provenance=list(item.provenance))
        )
    return normalized


def _normalize_experience(entries: list[ExperienceEntry]) -> list[ExperienceEntry]:
    normalized: list[ExperienceEntry] = []
    for entry in entries:
        normalized.append(
            ExperienceEntry(
                title=entry.title.strip() if entry.title else None,
                company=entry.company.strip() if entry.company else None,
                start_date=normalize_date(entry.start_date) if entry.start_date else None,
                end_date=normalize_date(entry.end_date) if entry.end_date else None,
                summary=entry.summary.strip() if entry.summary else None,
            )
        )
    return normalized


def _normalize_education(entries: list[EducationEntry]) -> list[EducationEntry]:
    normalized: list[EducationEntry] = []
    for entry in entries:
        normalized.append(
            EducationEntry(
                institution=entry.institution.strip() if entry.institution else None,
                degree=entry.degree.strip() if entry.degree else None,
                field=entry.field.strip() if entry.field else None,
                graduation_date=normalize_date(entry.graduation_date) if entry.graduation_date else None,
            )
        )
    return normalized


def normalize_profile(profile: ParsedProfile, config: AppConfig) -> ParsedProfile:
    """Return a copy of the profile with normalized scalar and list values."""
    normalized = ParsedProfile(
        source=profile.source,
        skill_confidence=profile.skill_confidence,
        experience_confidence=profile.experience_confidence,
        education_confidence=profile.education_confidence,
    )

    for name, field in profile.fields.items():
        if name in {"location", "total_years_experience"}:
            normalized.fields[name] = _normalize_scalar(name, field, config)
        else:
            normalized.fields[name] = FieldValue(
                value=str(field.value).strip() if field.value is not None else None,
                confidence=field.confidence,
                provenance=list(field.provenance),
            )

    normalized.emails = _normalize_contact_list(profile.emails, normalizer=normalize_email, config=config)
    normalized.phones = _normalize_contact_list(profile.phones, normalizer=normalize_phone, config=config)
    normalized.skills = canonicalize_skills(profile.skills, synonyms=config.skills_synonyms)
    normalized.experience = _normalize_experience(profile.experience)
    normalized.education = _normalize_education(profile.education)
    return normalized


def experience_to_dict(entry: ExperienceEntry) -> dict:
    payload: dict = {}
    if entry.company:
        payload["company"] = entry.company
    if entry.title:
        payload["title"] = entry.title
    if entry.start_date:
        payload["start"] = entry.start_date
    if entry.end_date:
        payload["end"] = entry.end_date
    if entry.summary:
        payload["summary"] = entry.summary
    return payload


def education_to_dict(entry: EducationEntry) -> dict:
    payload: dict = {}
    if entry.institution:
        payload["institution"] = entry.institution
    if entry.degree:
        payload["degree"] = entry.degree
    if entry.field:
        payload["field"] = entry.field
    if entry.graduation_date:
        payload["end_year"] = int(entry.graduation_date[:4])
    return payload
