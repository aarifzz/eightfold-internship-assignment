"""Location string normalization into a structured location object."""

from __future__ import annotations

import re

US_STATE_CODES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}

COUNTRY_ALIASES = {
    "us": "US",
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "united states": "US",
    "united states of america": "US",
    "uk": "GB",
    "u.k.": "GB",
    "united kingdom": "GB",
    "great britain": "GB",
    "in": "IN",
    "ind": "IN",
    "india": "IN",
    "bharat": "IN",
}

# Common Indian cities mapped to ISO country IN when seen in free-text locations.
INDIAN_CITIES = frozenset(
    {
        "chennai",
        "madras",
        "bengaluru",
        "bangalore",
        "mumbai",
        "bombay",
        "delhi",
        "new delhi",
        "hyderabad",
        "pune",
        "kolkata",
        "calcutta",
        "ahmedabad",
        "noida",
        "gurgaon",
        "gurugram",
        "jaipur",
        "lucknow",
        "kochi",
        "coimbatore",
        "visakhapatnam",
        "vizag",
        "chandigarh",
        "indore",
        "nagpur",
        "surat",
        "thiruvananthapuram",
        "trivandrum",
    }
)

# Indian states and union territories -> short region code.
INDIAN_STATES = {
    "andhra pradesh": "AP",
    "arunachal pradesh": "AR",
    "assam": "AS",
    "bihar": "BR",
    "chhattisgarh": "CG",
    "goa": "GA",
    "gujarat": "GJ",
    "haryana": "HR",
    "himachal pradesh": "HP",
    "jharkhand": "JH",
    "karnataka": "KA",
    "kerala": "KL",
    "madhya pradesh": "MP",
    "maharashtra": "MH",
    "manipur": "MN",
    "meghalaya": "ML",
    "mizoram": "MZ",
    "nagaland": "NL",
    "odisha": "OR",
    "orissa": "OR",
    "punjab": "PB",
    "rajasthan": "RJ",
    "sikkim": "SK",
    "tamil nadu": "TN",
    "telangana": "TG",
    "tripura": "TR",
    "uttar pradesh": "UP",
    "uttarakhand": "UK",
    "west bengal": "WB",
    "delhi": "DL",
    "new delhi": "DL",
}


def _normalize_us_state(token: str) -> str | None:
    cleaned = token.strip()
    if not cleaned:
        return None
    upper = cleaned.upper()
    if len(upper) == 2 and upper.isalpha():
        return upper
    return US_STATE_CODES.get(cleaned.lower())


def _normalize_indian_region(token: str) -> str | None:
    cleaned = token.strip()
    if not cleaned:
        return None
    return INDIAN_STATES.get(cleaned.lower())


def _is_indian_city(city: str | None) -> bool:
    return bool(city and city.strip().lower() in INDIAN_CITIES)


def _is_indian_region(token: str) -> bool:
    return token.strip().lower() in INDIAN_STATES


def _looks_like_indian_location(parts: list[str], city: str | None) -> bool:
    if _is_indian_city(city):
        return True
    return any(_is_indian_region(part) for part in parts[1:])


def _normalize_country(token: str, *, default_country: str) -> str:
    cleaned = token.strip()
    if not cleaned:
        return default_country
    if len(cleaned) == 2 and cleaned.isalpha():
        return cleaned.upper()
    return COUNTRY_ALIASES.get(cleaned.lower(), default_country)


def normalize_location(raw: str | None, *, default_country: str = "US") -> dict[str, str] | None:
    """
    Parse a free-text location into {city, region, country}.

    Country codes are normalized to ISO-3166 alpha-2.
    Common Indian cities/states resolve to country IN.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None

    parts = [part.strip() for part in text.split(",") if part.strip()]
    city: str | None = None
    region: str | None = None
    country = default_country

    if len(parts) == 1:
        city = parts[0]
        if _is_indian_city(city):
            country = "IN"
    elif len(parts) == 2:
        city = parts[0]
        second = parts[1]
        if _looks_like_indian_location(parts, city):
            country = "IN"
            region = _normalize_indian_region(second) or second
        else:
            region_guess = _normalize_us_state(second)
            if region_guess:
                region = region_guess
                country = "US"
            else:
                country = _normalize_country(second, default_country=default_country)
    else:
        city = parts[0]
        if _looks_like_indian_location(parts, city):
            country = "IN"
            region = _normalize_indian_region(parts[1]) or parts[1]
            if len(parts) > 2:
                country = _normalize_country(parts[-1], default_country="IN")
        else:
            region = _normalize_us_state(parts[1])
            country = _normalize_country(parts[-1], default_country=default_country)
            if region:
                country = "US"

    result: dict[str, str] = {"country": country}
    if city:
        result["city"] = city
    if region:
        result["region"] = region
    return result


def extract_location_from_header(line: str) -> str | None:
    """Pull location from resume header lines like 'Title | City, ST'."""
    if "|" not in line:
        return None
    _, right = line.split("|", 1)
    candidate = right.strip()
    if re.search(r"[A-Za-z]", candidate) and "," in candidate:
        return candidate
    return None
