"""Unit tests for JSON schema validation."""

import pytest
from jsonschema import ValidationError

from eightfold_profile.config import AppConfig
from eightfold_profile.validation import schema_for_config, validate_output


def _full_payload() -> dict:
    return {
        "candidate_id": "CAND-1001",
        "full_name": "Jane Doe",
        "emails": ["jane.doe@example.com"],
        "phones": ["+14155550199"],
        "location": {
            "city": "San Francisco",
            "region": "CA",
            "country": "US",
        },
        "links": {
            "linkedin": "https://linkedin.com/in/janedoe",
            "github": "https://github.com/janedoe",
            "portfolio": None,
            "other": [],
        },
        "headline": "Senior Software Engineer",
        "years_experience": 7,
        "skills": [{"name": "Python", "confidence": 0.9, "sources": ["recruiter_csv"]}],
        "experience": [
            {
                "company": "Acme",
                "title": "Engineer",
                "start": "2022-01",
                "summary": "Built APIs",
            }
        ],
        "education": [
            {
                "institution": "State University",
                "degree": "B.S.",
                "field": "Computer Science",
                "end_year": 2018,
            }
        ],
        "provenance": [
            {
                "field": "emails[0]",
                "source": "recruiter_csv",
                "method": "csv_parser.parse_recruiter_csv",
            }
        ],
        "overall_confidence": 0.91,
    }


def test_validate_assignment_profile_shape_with_confidence_enabled():
    config = AppConfig(include_confidence=True, include_provenance=True)
    validate_output(_full_payload(), config=config)


def test_validate_plain_profile_when_confidence_disabled():
    config = AppConfig(include_confidence=False, include_provenance=False)
    payload = {
        "candidate_id": "CAND-1001",
        "full_name": "Jane Doe",
        "emails": ["jane.doe@example.com"],
        "phones": ["+14155550199"],
        "skills": [{"name": "Python", "confidence": 0.9, "sources": ["recruiter_csv"]}],
        "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
        "experience": [],
        "education": [],
    }
    validate_output(payload, config=config)


def test_validate_allows_missing_overall_confidence_when_disabled():
    config = AppConfig(include_confidence=False, include_provenance=False)
    schema = schema_for_config(config)
    assert "overall_confidence" not in schema["properties"]
    validate_output(
        {
            "emails": ["a@example.com"],
            "skills": [{"name": "Python", "confidence": 0.5, "sources": ["resume_pdf"]}],
            "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
        },
        config=config,
    )


def test_validate_rejects_invalid_phone():
    config = AppConfig(include_confidence=True, include_provenance=False)
    payload = {
        "phones": ["555-0199"],
        "emails": [],
        "skills": [],
        "experience": [],
        "education": [],
        "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
    }
    with pytest.raises(ValidationError):
        validate_output(payload, config=config)
