"""Core data models for parsed, merged, and projected candidate profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    """Known input sources for provenance tracking."""

    RECRUITER_CSV = "recruiter_csv"
    RESUME_PDF = "resume_pdf"


@dataclass(frozen=True)
class Provenance:
    """Where a single field value originated."""

    source: SourceType
    raw_value: Any
    extractor: str
    field_path: str


@dataclass
class FieldValue:
    """A normalized value with confidence and provenance."""

    value: Any
    confidence: float
    provenance: list[Provenance] = field(default_factory=list)


@dataclass
class SkillValue:
    """Canonical skill with per-skill confidence and contributing sources."""

    name: str
    confidence: float
    sources: list[SourceType] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)


@dataclass
class ExperienceEntry:
    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    summary: str | None = None


@dataclass
class EducationEntry:
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    graduation_date: str | None = None


@dataclass
class ParsedProfile:
    """Partial profile extracted from a single source."""

    source: SourceType
    fields: dict[str, FieldValue] = field(default_factory=dict)
    emails: list[FieldValue] = field(default_factory=list)
    phones: list[FieldValue] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    skill_confidence: float = 0.0
    experience_confidence: float = 0.0
    education_confidence: float = 0.0


# Internal scalar fields used during parsing/merging (before canonical assembly).
INTERNAL_SCALAR_FIELDS = (
    "candidate_id",
    "first_name",
    "last_name",
    "full_name",
    "current_title",
    "current_company",
    "linkedin_url",
    "github_url",
    "total_years_experience",
    "summary",
)

# Default assignment output schema field names.
DEFAULT_OUTPUT_FIELDS = [
    "candidate_id",
    "full_name",
    "emails",
    "phones",
    "location",
    "links",
    "headline",
    "years_experience",
    "skills",
    "experience",
    "education",
    "provenance",
    "overall_confidence",
]

# Backward-compatible aliases used by the merger.
CANONICAL_SCALAR_FIELDS = INTERNAL_SCALAR_FIELDS
CANONICAL_OBJECT_FIELDS = ("location", "links")
CANONICAL_LIST_FIELDS = ("emails", "phones", "skills", "experience", "education")
CANONICAL_META_FIELDS = ("provenance", "overall_confidence")
DEFAULT_CANONICAL_FIELDS = list(DEFAULT_OUTPUT_FIELDS)
