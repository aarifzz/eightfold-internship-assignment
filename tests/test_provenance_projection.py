"""Unit tests for provenance projection."""

from eightfold_profile.config import AppConfig
from eightfold_profile.projection.provenance_projection import project_provenance
from eightfold_profile.projection.projector import project_profile


def test_project_provenance_maps_internal_fields_to_output_schema():
    output = {
        "full_name": "Jane Doe",
        "headline": "Engineer",
        "years_experience": 7,
        "emails": ["jane@example.com"],
        "links": {"linkedin": "https://linkedin.com/in/jane", "github": None, "portfolio": None, "other": []},
        "skills": [{"name": "Python", "confidence": 0.9, "sources": ["recruiter_csv"]}],
    }
    canonical_provenance = [
        {"field": "first_name", "source": "recruiter_csv", "method": "csv_parser"},
        {"field": "last_name", "source": "recruiter_csv", "method": "csv_parser"},
        {"field": "current_title", "source": "recruiter_csv", "method": "csv_parser"},
        {"field": "total_years_experience", "source": "recruiter_csv", "method": "csv_parser"},
        {"field": "current_company", "source": "recruiter_csv", "method": "csv_parser"},
        {"field": "linkedin_url", "source": "recruiter_csv", "method": "csv_parser"},
        {"field": "emails[0]", "source": "recruiter_csv", "method": "csv_parser"},
        {"field": "skills[0].name", "source": "recruiter_csv", "method": "csv_parser"},
    ]

    projected = project_provenance(canonical_provenance, output)
    fields = {row["field"] for row in projected}

    assert "first_name" not in fields
    assert "last_name" not in fields
    assert "current_title" not in fields
    assert "current_company" not in fields
    assert "total_years_experience" not in fields
    assert "linkedin_url" not in fields
    assert "full_name" in fields
    assert "headline" in fields
    assert "years_experience" in fields
    assert "links.linkedin" in fields
    assert "emails[0]" in fields
    assert "skills[0].name" in fields


def test_project_profile_replaces_canonical_provenance():
    canonical = {
        "full_name": "Jane Doe",
        "headline": "Engineer",
        "emails": ["jane@example.com"],
        "skills": [{"name": "Python", "confidence": 0.9, "sources": ["recruiter_csv"]}],
        "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
        "provenance": [
            {"field": "first_name", "source": "recruiter_csv", "method": "csv_parser"},
            {"field": "summary", "source": "recruiter_csv", "method": "csv_parser"},
        ],
    }
    config = AppConfig(
        output_fields=["full_name", "headline", "emails", "skills", "links", "provenance"],
        include_provenance=True,
        include_confidence=False,
    )

    projected = project_profile(canonical, config)
    fields = {row["field"] for row in projected["provenance"]}

    assert "first_name" not in fields
    assert "summary" not in fields
    assert "full_name" in fields
    assert "headline" in fields
