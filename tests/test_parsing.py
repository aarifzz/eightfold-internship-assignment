"""Unit tests for resume PDF parsing heuristics."""

from pathlib import Path

import pytest

from eightfold_profile.parsing.pdf_parser import parse_resume_pdf

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


@pytest.fixture(scope="module", autouse=True)
def ensure_sample_pdf():
    import subprocess
    import sys

    pdf_path = SAMPLES / "resume.pdf"
    if not pdf_path.exists():
        script = Path(__file__).resolve().parents[1] / "scripts" / "generate_sample_pdf.py"
        subprocess.run([sys.executable, str(script)], check=True)


def test_parse_experience_separates_fields():
    profile = parse_resume_pdf(SAMPLES / "resume.pdf")
    assert profile.experience
    latest = profile.experience[0]
    assert latest.title == "Senior Software Engineer"
    assert latest.company == "Acme Corp"
    assert latest.start_date == "Jan 2022"
    assert latest.end_date == "Present"
    assert latest.summary and "APIs" in latest.summary


def test_parse_education_extracts_components():
    profile = parse_resume_pdf(SAMPLES / "resume.pdf")
    assert profile.education
    entry = profile.education[0]
    assert entry.degree
    assert entry.field == "Computer Science"
    assert entry.institution == "State University"
    assert entry.graduation_date == "2018"


def test_parse_collects_multiple_contacts():
    profile = parse_resume_pdf(SAMPLES / "resume.pdf")
    assert len(profile.emails) == 1
    assert len(profile.phones) == 1
