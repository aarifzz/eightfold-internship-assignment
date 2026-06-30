"""Unit tests for confidence-based merging."""

from eightfold_profile.confidence import Scorer
from eightfold_profile.merging import merge_profiles
from eightfold_profile.models import FieldValue, ParsedProfile, Provenance, SourceType


def _scalar(source: SourceType, field: str, value: str, confidence: float) -> FieldValue:
    return FieldValue(
        value=value,
        confidence=confidence,
        provenance=[
            Provenance(
                source=source,
                raw_value=value,
                extractor="test",
                field_path=field,
            )
        ],
    )


def _email(source: SourceType, value: str, confidence: float, index: int = 0) -> FieldValue:
    return FieldValue(
        value=value,
        confidence=confidence,
        provenance=[
            Provenance(
                source=source,
                raw_value=value,
                extractor="test",
                field_path=f"emails[{index}]",
            )
        ],
    )


def test_merge_prefers_higher_confidence_email():
    csv_profile = ParsedProfile(source=SourceType.RECRUITER_CSV)
    csv_profile.emails = [_email(SourceType.RECRUITER_CSV, "jane.doe@example.com", 0.97)]

    pdf_profile = ParsedProfile(source=SourceType.RESUME_PDF)
    pdf_profile.emails = [_email(SourceType.RESUME_PDF, "jane.doe@work-email.com", 0.88)]

    merged = merge_profiles([csv_profile, pdf_profile])
    assert merged.emails[0].value == "jane.doe@example.com"
    assert len(merged.emails) == 2


def test_merge_unions_skills_with_confidence_and_sources():
    csv_profile = ParsedProfile(source=SourceType.RECRUITER_CSV)
    csv_profile.skills = ["Python", "AWS"]
    csv_profile.skill_confidence = 0.9

    pdf_profile = ParsedProfile(source=SourceType.RESUME_PDF)
    pdf_profile.skills = ["JavaScript", "Python"]
    pdf_profile.skill_confidence = 0.75

    merged = merge_profiles([csv_profile, pdf_profile])
    assert {skill.name for skill in merged.skills} == {"AWS", "JavaScript", "Python"}
    python = next(skill for skill in merged.skills if skill.name == "Python")
    assert python.confidence > 0.9
    assert {source.value for source in python.sources} == {"recruiter_csv", "resume_pdf"}


def test_conflict_email_primary_is_higher_confidence_source():
    csv_profile = ParsedProfile(source=SourceType.RECRUITER_CSV)
    csv_profile.emails = [_email(SourceType.RECRUITER_CSV, "jane.doe@example.com", 0.97)]

    pdf_profile = ParsedProfile(source=SourceType.RESUME_PDF)
    pdf_profile.emails = [_email(SourceType.RESUME_PDF, "jane.doe@work-email.com", 0.88)]

    merged = merge_profiles([csv_profile, pdf_profile])
    assert merged.emails[0].value == "jane.doe@example.com"
    assert merged.emails[0].provenance[0].source == SourceType.RECRUITER_CSV


def test_scorer_source_bonus():
    scorer = Scorer()
    assert scorer.source_bonus(SourceType.RECRUITER_CSV, "emails") > 0
