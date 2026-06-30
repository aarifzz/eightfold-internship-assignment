"""Confidence scoring for extracted field values."""

from __future__ import annotations

from eightfold_profile.models import EducationEntry, ExperienceEntry, SourceType


class Scorer:
    """
    Heuristic confidence model.

    Structured CSV fields receive higher base confidence than PDF heuristics.
    Values are in [0, 1].
    """

    CSV_BASE = 0.92
    PDF_BASE = 0.72

    def csv_scalar_confidence(self, field_name: str, raw_value: object) -> float:
        if raw_value is None or str(raw_value).strip() == "":
            return 0.0
        if field_name in {"candidate_id", "email", "emails"}:
            return 0.97
        if field_name in {"phone", "phones"}:
            return 0.94
        return self.CSV_BASE

    def csv_skills_confidence(self, has_skills: bool) -> float:
        return 0.9 if has_skills else 0.0

    def pdf_name_confidence(self, name: str | None) -> float:
        if not name:
            return 0.0
        tokens = name.split()
        if 1 <= len(tokens) <= 4:
            return 0.78
        return 0.55

    def pdf_email_confidence(self, email: str | None) -> float:
        return 0.88 if email else 0.0

    def pdf_phone_confidence(self, phone: str | None) -> float:
        return 0.82 if phone else 0.0

    def pdf_url_confidence(self, url: str | None) -> float:
        return 0.85 if url else 0.0

    def pdf_skills_confidence(self, skills: list[str]) -> float:
        if not skills:
            return 0.0
        return min(0.8, 0.55 + 0.03 * len(skills))

    def pdf_experience_confidence(self, entries: list[ExperienceEntry]) -> float:
        if not entries:
            return 0.0
        scored = 0.0
        for entry in entries:
            parts = sum(
                1
                for value in (entry.title, entry.company, entry.start_date, entry.end_date, entry.summary)
                if value
            )
            scored += min(0.75, 0.3 + 0.09 * parts)
        return min(0.85, scored / len(entries))

    def pdf_education_confidence(self, entries: list[EducationEntry]) -> float:
        if not entries:
            return 0.0
        scored = 0.0
        for entry in entries:
            parts = sum(1 for value in (entry.institution, entry.degree, entry.field, entry.graduation_date) if value)
            scored += min(0.8, 0.35 + 0.1 * parts)
        return min(0.85, scored / len(entries))

    def source_bonus(self, source: SourceType, field_name: str) -> float:
        """Small tie-breaker favoring structured source for HR-maintained fields."""
        hr_fields = {
            "candidate_id",
            "email",
            "emails",
            "phone",
            "phones",
            "location",
            "current_title",
            "current_company",
            "total_years_experience",
        }
        if field_name in hr_fields and source == SourceType.RECRUITER_CSV:
            return 0.02
        if field_name in {"skills", "summary", "full_name"} and source == SourceType.RESUME_PDF:
            return 0.02
        return 0.0

    def merged_confidence(self, confidence: float, num_sources: int) -> float:
        """Boost confidence slightly when multiple sources agree."""
        if num_sources <= 1:
            return confidence
        return min(1.0, confidence + 0.05 * (num_sources - 1))
