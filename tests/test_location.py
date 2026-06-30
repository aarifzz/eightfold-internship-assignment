"""Unit tests for location normalization."""

from eightfold_profile.normalization.location import normalize_location


def test_normalize_location_city_region_us():
    result = normalize_location("San Francisco, CA", default_country="US")
    assert result == {
        "country": "US",
        "city": "San Francisco",
        "region": "CA",
    }


def test_normalize_location_indian_city_state():
    result = normalize_location("Chennai, Tamil Nadu", default_country="US")
    assert result == {
        "country": "IN",
        "city": "Chennai",
        "region": "TN",
    }


def test_normalize_location_indian_city_only():
    result = normalize_location("Bengaluru", default_country="US")
    assert result == {
        "country": "IN",
        "city": "Bengaluru",
    }


def test_normalize_location_mumbai_maharashtra():
    result = normalize_location("Mumbai, Maharashtra", default_country="US")
    assert result == {
        "country": "IN",
        "city": "Mumbai",
        "region": "MH",
    }
