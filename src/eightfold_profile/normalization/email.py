"""Email normalization."""

from __future__ import annotations

import re


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    email = value.strip().lower()
    if not email:
        return None
    if not EMAIL_RE.match(email):
        raise ValueError(f"invalid email format: {value!r}")
    return email
