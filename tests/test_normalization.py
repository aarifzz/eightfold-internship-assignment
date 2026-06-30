"""Unit tests for normalization helpers."""

import pytest

from eightfold_profile.normalization.dates import normalize_date
from eightfold_profile.normalization.email import normalize_email
from eightfold_profile.normalization.phone import normalize_phone
from eightfold_profile.normalization.skills import canonicalize_skills


def test_normalize_email_lowercases():
    assert normalize_email("Jane.Doe@Example.COM") == "jane.doe@example.com"


def test_normalize_phone_e164_us():
    assert normalize_phone("(415) 555-0199", default_region="US") == "+14155550199"


def test_normalize_date_variants():
    assert normalize_date("Jan 2022") == "2022-01"
    assert normalize_date("06/2018") == "2018-06"
    assert normalize_date("2018") == "2018-01"
    assert normalize_date("2020-05") == "2020-05"
    assert normalize_date("Present") is None


def test_canonicalize_skills_dedupes_and_maps_synonyms():
    skills = canonicalize_skills(["python", "Python", "k8s", "JavaScript", "js"])
    assert skills == ["JavaScript", "Kubernetes", "Python"]


def test_invalid_email_raises():
    with pytest.raises(ValueError):
        normalize_email("not-an-email")
