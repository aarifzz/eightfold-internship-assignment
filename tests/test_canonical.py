"""Unit tests for canonical profile assembly."""

from eightfold_profile.canonical import build_canonical_profile
from eightfold_profile.canonical.builder import _dedupe_provenance
from eightfold_profile.config import AppConfig
from eightfold_profile.merging import merge_profiles
from eightfold_profile.models import ParsedProfile, SourceType


def test_dedupe_provenance_removes_duplicate_field_source_method():
    records = [
        {
            "field": "full_name",
            "source": "recruiter_csv",
            "method": "csv_parser.parse_recruiter_csv",
        },
        {
            "field": "full_name",
            "source": "recruiter_csv",
            "method": "csv_parser.parse_recruiter_csv",
        },
        {
            "field": "full_name",
            "source": "resume_pdf",
            "method": "pdf_parser.parse_resume_pdf",
        },
    ]
    deduped = _dedupe_provenance(records)
    assert len(deduped) == 2


def test_build_canonical_matches_assignment_schema_shape():
    profile = ParsedProfile(source=SourceType.RECRUITER_CSV)
    profile.skills = ["Python"]
    profile.skill_confidence = 0.9
    merged = merge_profiles([profile, ParsedProfile(source=SourceType.RESUME_PDF)])
    canonical = build_canonical_profile(merged, AppConfig(include_confidence=True, include_provenance=True))
    assert "links" in canonical
    assert "headline" in canonical
    assert "years_experience" in canonical
    assert canonical["skills"][0]["sources"] == ["recruiter_csv"]
    assert canonical["emails"] == []
    assert all("method" in row for row in canonical.get("provenance", []))
