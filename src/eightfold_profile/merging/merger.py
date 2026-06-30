"""Confidence-based profile merging with provenance preservation."""

from __future__ import annotations

from dataclasses import dataclass, field

from eightfold_profile.confidence.scorer import Scorer
from eightfold_profile.models import (
    CANONICAL_SCALAR_FIELDS,
    EducationEntry,
    ExperienceEntry,
    FieldValue,
    ParsedProfile,
    Provenance,
    SkillValue,
)
from eightfold_profile.normalization import education_to_dict, experience_to_dict
from eightfold_profile.normalization.skills import canonicalize_skill


@dataclass
class MergedProfile:
    """Canonical in-memory profile before projection."""

    scalars: dict[str, FieldValue] = field(default_factory=dict)
    emails: list[FieldValue] = field(default_factory=list)
    phones: list[FieldValue] = field(default_factory=list)
    location: FieldValue | None = None
    skills: list[SkillValue] = field(default_factory=list)
    experience: FieldValue | None = None
    education: FieldValue | None = None


def _effective_confidence(field_name: str, candidate: FieldValue, scorer: Scorer) -> float:
    bonus = 0.0
    for record in candidate.provenance:
        bonus = max(bonus, scorer.source_bonus(record.source, field_name))
    return candidate.confidence + bonus


def _pick_scalar(
    field_name: str,
    values: list[FieldValue],
    scorer: Scorer,
) -> FieldValue | None:
    if not values:
        return None
    ranked = sorted(
        values,
        key=lambda item: (_effective_confidence(field_name, item, scorer), len(item.provenance)),
        reverse=True,
    )
    winner = ranked[0]
    agreeing = [item for item in ranked if item.value == winner.value]
    merged_provenance: list[Provenance] = []
    for item in agreeing:
        merged_provenance.extend(item.provenance)
    confidence = scorer.merged_confidence(winner.confidence, len(agreeing))
    return FieldValue(value=winner.value, confidence=confidence, provenance=merged_provenance)


def _merge_contacts(
    profiles: list[ParsedProfile],
    attr: str,
    field_name: str,
    scorer: Scorer,
) -> list[FieldValue]:
    by_value: dict[str, FieldValue] = {}
    for profile in profiles:
        for item in getattr(profile, attr):
            key = str(item.value).lower()
            existing = by_value.get(key)
            if existing is None:
                by_value[key] = FieldValue(
                    value=item.value,
                    confidence=_effective_confidence(field_name, item, scorer),
                    provenance=list(item.provenance),
                )
                continue
            merged_confidence = scorer.merged_confidence(
                max(existing.confidence, _effective_confidence(field_name, item, scorer)),
                2,
            )
            by_value[key] = FieldValue(
                value=item.value,
                confidence=merged_confidence,
                provenance=existing.provenance + item.provenance,
            )
    return sorted(by_value.values(), key=lambda item: item.confidence, reverse=True)


def _merge_skills(profiles: list[ParsedProfile], scorer: Scorer) -> list[SkillValue]:
    skill_map: dict[str, SkillValue] = {}
    for profile in profiles:
        for raw_skill in profile.skills:
            canonical = canonicalize_skill(raw_skill)
            key = canonical.lower()
            confidence = scorer.merged_confidence(profile.skill_confidence, 1)
            provenance = [
                Provenance(
                    source=profile.source,
                    raw_value=raw_skill,
                    extractor="normalization.canonicalize_skills",
                    field_path="skills",
                )
            ]
            existing = skill_map.get(key)
            if existing is None:
                skill_map[key] = SkillValue(
                    name=canonical,
                    confidence=confidence,
                    sources=[profile.source],
                    provenance=provenance,
                )
            else:
                merged_sources = list(dict.fromkeys(existing.sources + [profile.source]))
                skill_map[key] = SkillValue(
                    name=canonical,
                    confidence=scorer.merged_confidence(max(existing.confidence, confidence), 2),
                    sources=merged_sources,
                    provenance=existing.provenance + provenance,
                )
    return sorted(skill_map.values(), key=lambda item: item.name.lower())


def _entry_key(entry: ExperienceEntry | EducationEntry) -> tuple:
    if isinstance(entry, ExperienceEntry):
        return (
            (entry.title or "").lower(),
            (entry.company or "").lower(),
            entry.start_date or "",
        )
    return (
        (entry.institution or "").lower(),
        (entry.degree or "").lower(),
        entry.graduation_date or "",
    )


def _merge_list_entries(
    profiles: list[ParsedProfile],
    attr: str,
    confidence_attr: str,
    to_dict,
    scorer: Scorer,
) -> FieldValue | None:
    ranked_profiles = sorted(
        profiles,
        key=lambda profile: getattr(profile, confidence_attr),
        reverse=True,
    )
    merged: list = []
    seen: set[tuple] = set()
    provenance: list[Provenance] = []
    best_confidence = 0.0

    for profile in ranked_profiles:
        entries = getattr(profile, attr)
        if not entries:
            continue
        best_confidence = max(best_confidence, getattr(profile, confidence_attr))
        provenance.append(
            Provenance(
                source=profile.source,
                raw_value=[to_dict(entry) for entry in entries],
                extractor=f"merger._merge_list_entries.{attr}",
                field_path=attr,
            )
        )
        for entry in entries:
            key = _entry_key(entry)
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)

    if not merged:
        return None
    return FieldValue(
        value=[to_dict(entry) for entry in merged],
        confidence=scorer.merged_confidence(best_confidence, len(provenance)),
        provenance=provenance,
    )


def merge_profiles(profiles: list[ParsedProfile]) -> MergedProfile:
    """Merge multiple parsed profiles into one canonical profile."""
    if not profiles:
        raise ValueError("at least one parsed profile is required")

    scorer = Scorer()
    merged = MergedProfile()

    for field_name in CANONICAL_SCALAR_FIELDS:
        candidates = [profile.fields[field_name] for profile in profiles if field_name in profile.fields]
        picked = _pick_scalar(field_name, candidates, scorer)
        if picked is not None:
            merged.scalars[field_name] = picked

    location_candidates = [profile.fields["location"] for profile in profiles if "location" in profile.fields]
    merged.location = _pick_scalar("location", location_candidates, scorer)

    merged.emails = _merge_contacts(profiles, "emails", "emails", scorer)
    merged.phones = _merge_contacts(profiles, "phones", "phones", scorer)
    merged.skills = _merge_skills(profiles, scorer)
    merged.experience = _merge_list_entries(
        profiles, "experience", "experience_confidence", experience_to_dict, scorer
    )
    merged.education = _merge_list_entries(
        profiles, "education", "education_confidence", education_to_dict, scorer
    )
    return merged
