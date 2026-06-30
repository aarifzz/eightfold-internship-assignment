"""Phone normalization to E.164."""

from __future__ import annotations

import phonenumbers
from phonenumbers import NumberParseException


def normalize_phone(value: str | None, *, default_region: str = "US") -> str | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except NumberParseException as exc:
        raise ValueError(f"invalid phone number: {value!r}") from exc
    if not phonenumbers.is_possible_number(parsed):
        raise ValueError(f"phone number not possible: {value!r}")
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(f"phone number not valid: {value!r}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
