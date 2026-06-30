"""Date normalization to YYYY-MM."""

from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as date_parser

MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}

PRESENT_TOKENS = {"present", "current", "now", "ongoing"}


def normalize_date(value: str | None) -> str | None:
    """
    Normalize flexible date strings to YYYY-MM.

    Present/current values return None (open-ended employment/education).
    Year-only values become YYYY-01.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.lower() in PRESENT_TOKENS:
        return None

    if re.fullmatch(r"\d{4}-\d{2}", text):
        year, month = text.split("-")
        if 1 <= int(month) <= 12:
            return text
        raise ValueError(f"invalid month in date: {value!r}")

    if re.fullmatch(r"\d{4}", text):
        return f"{text}-01"

    month_year = re.match(
        r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})$",
        text,
        re.I,
    )
    if month_year:
        month = MONTH_MAP[month_year.group(1).lower()[:3]]
        return f"{month_year.group(2)}-{month}"

    mm_yyyy = re.fullmatch(r"(\d{1,2})/(\d{4})", text)
    if mm_yyyy:
        month = int(mm_yyyy.group(1))
        if not 1 <= month <= 12:
            raise ValueError(f"invalid month in date: {value!r}")
        return f"{mm_yyyy.group(2)}-{month:02d}"

    try:
        parsed: datetime = date_parser.parse(text, default=datetime(2000, 1, 1))
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"unable to parse date: {value!r}") from exc
    return parsed.strftime("%Y-%m")
