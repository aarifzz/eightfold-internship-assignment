"""Integration tests for the end-to-end pipeline."""

from pathlib import Path

import pytest

from eightfold_profile.canonical import build_canonical_profile
from eightfold_profile.config import AppConfig, MissingValueBehavior
from eightfold_profile.merging import merge_profiles
from eightfold_profile.normalization import normalize_profile
from eightfold_profile.parsing import parse_recruiter_csv, parse_resume_pdf
from eightfold_profile.pipeline import PipelineError, build_candidate_profile, build_from_paths
from eightfold_profile.projection import ProjectionError, project_profile

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "sample_config.json"


@pytest.fixture(scope="module", autouse=True)
def ensure_sample_pdf():
    import subprocess
    import sys

    pdf_path = SAMPLES / "resume.pdf"
    if not pdf_path.exists():
        script = Path(__file__).resolve().parents[1] / "scripts" / "generate_sample_pdf.py"
        subprocess.run([sys.executable, str(script)], check=True)


def test_pipeline_builds_valid_profile():
    profile = build_candidate_profile(
        csv_path=SAMPLES / "recruiter.csv",
        pdf_path=SAMPLES / "resume.pdf",
        config=AppConfig(include_confidence=True, include_provenance=True),
        candidate_id="CAND-1001",
    )
    assert profile["candidate_id"] == "CAND-1001"
    assert profile["emails"][0] == "jane.doe@example.com"
    assert profile["phones"][0] == "+14155550199"
    assert profile["location"]["city"] == "San Francisco"
    assert profile["location"]["region"] == "CA"
    assert profile["location"]["country"] == "US"
    assert profile["links"]["linkedin"] == "https://linkedin.com/in/janedoe"
    assert profile["headline"] == "Strong backend focus with distributed systems experience."
    assert profile["years_experience"] == 7.0
    python = next(skill for skill in profile["skills"] if skill["name"] == "Python")
    assert "recruiter_csv" in python["sources"]
    assert profile["overall_confidence"] > 0
    provenance_fields = {row["field"] for row in profile["provenance"]}
    assert "first_name" not in provenance_fields
    assert "last_name" not in provenance_fields
    assert "current_title" not in provenance_fields
    assert profile["provenance"][0]["method"]
    assert profile["experience"][0]["company"] == "Acme Corp"
    assert profile["experience"][0]["title"] == "Senior Software Engineer"
    assert profile["experience"][0]["start"] == "2022-01"
    assert profile["education"][0]["end_year"] == 2018


def test_conflict_email_orders_higher_confidence_first():
    profile = build_from_paths(
        csv_path=SAMPLES / "recruiter.csv",
        pdf_path=SAMPLES / "resume.pdf",
        config_path=CONFIG,
        candidate_id="CAND-1001",
    )
    assert profile["emails"][0] == "jane.doe@example.com"
    assert profile["emails"][1] == "jane.doe@work-email.com"


def test_pipeline_csv_only_when_pdf_missing(tmp_path: Path):
    profile = build_candidate_profile(
        csv_path=SAMPLES / "recruiter.csv",
        pdf_path=tmp_path / "missing.pdf",
        candidate_id="CAND-1001",
    )
    assert profile["candidate_id"] == "CAND-1001"
    assert profile["emails"][0] == "jane.doe@example.com"
    assert profile["skills"]


def test_pipeline_csv_only_when_pdf_malformed(tmp_path: Path):
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"not a valid pdf")
    profile = build_candidate_profile(
        csv_path=SAMPLES / "recruiter.csv",
        pdf_path=bad_pdf,
        candidate_id="CAND-1001",
    )
    assert profile["candidate_id"] == "CAND-1001"
    assert profile["emails"][0] == "jane.doe@example.com"
    assert profile["experience"] == []


def test_pipeline_pdf_only_with_deterministic_id():
    profile = build_candidate_profile(
        pdf_path=SAMPLES / "resume.pdf",
    )
    # resume.pdf contains email jane.doe@work-email.com
    assert profile["candidate_id"] == "jane.doe@work-email.com"
    assert profile["full_name"] == "Jane Doe"


def test_pipeline_csv_only_with_explicit_none():
    profile = build_candidate_profile(
        csv_path=SAMPLES / "recruiter.csv",
        pdf_path=None,
        candidate_id="CAND-1001",
    )
    assert profile["candidate_id"] == "CAND-1001"
    assert profile["emails"] == ["jane.doe@example.com"]


def test_pipeline_no_sources_raises():
    with pytest.raises(PipelineError, match="No valid input sources"):
        build_candidate_profile(csv_path=None, pdf_path=None)


def test_missing_value_error_behavior():
    csv_profile = parse_recruiter_csv(SAMPLES / "recruiter.csv", candidate_id="CAND-1001")
    pdf_profile = parse_resume_pdf(SAMPLES / "resume.pdf")
    config = AppConfig(
        output_fields=["candidate_id", "emails", "missing_field"],
        missing_value_behavior=MissingValueBehavior.ERROR,
        include_confidence=False,
        include_provenance=False,
    )
    merged = merge_profiles(
        [normalize_profile(csv_profile, config), normalize_profile(pdf_profile, config)]
    )
    canonical = build_canonical_profile(merged, config)
    with pytest.raises(ProjectionError):
        project_profile(canonical, config)


def test_pipeline_missing_csv_succeeds_if_pdf_present():
    # Requirement 6: Missing source should not crash if another is valid
    profile = build_from_paths(
        csv_path=SAMPLES / "missing.csv",
        pdf_path=SAMPLES / "resume.pdf",
    )
    assert profile["candidate_id"] == "jane.doe@work-email.com"


def test_pipeline_missing_both_raises():
    with pytest.raises(PipelineError):
        build_from_paths(
            csv_path=SAMPLES / "missing.csv",
            pdf_path=SAMPLES / "missing.pdf",
        )


def test_pipeline_minimal_config_without_confidence_metadata():
    minimal_config = SAMPLES.parent / "config" / "minimal_config.json"
    profile = build_from_paths(
        csv_path=SAMPLES / "recruiter.csv",
        pdf_path=SAMPLES / "resume.pdf",
        config_path=minimal_config,
        candidate_id="CAND-1001",
    )
    assert "overall_confidence" not in profile
    assert "provenance" not in profile
    assert profile["emails"] == ["jane.doe@example.com", "jane.doe@work-email.com"]
    assert profile["skills"][0]["name"] == "AWS"
