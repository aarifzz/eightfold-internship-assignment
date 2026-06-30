"""Unstructured resume PDF parsing via text extraction and heuristics."""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from eightfold_profile.confidence.scorer import Scorer
from eightfold_profile.models import (
    EducationEntry,
    ExperienceEntry,
    FieldValue,
    ParsedProfile,
    Provenance,
    SourceType,
)
from eightfold_profile.normalization.location import extract_location_from_header


class PDFParseError(ValueError):
    """Raised when resume PDF cannot be parsed."""


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}\b"
)
LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w%-]+", re.I)
GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/[\w%-]+", re.I)
DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|"
    r"\d{4}-\d{2}|\d{2}/\d{4}|\d{4})\s*[-–—to]+\s*"
    r"(?P<end>Present|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|"
    r"\d{4}-\d{2}|\d{2}/\d{4}|\d{4})",
    re.I,
)
SECTION_BREAK_RE = re.compile(
    r"^(skills|technical skills|core competencies|education|experience|work experience|"
    r"employment|projects|certifications|summary)\s*:?\s*$",
    re.I,
)
SKILLS_HEADER_RE = re.compile(r"^(skills|technical skills|core competencies)\s*:?\s*$", re.I)
EDUCATION_HEADER_RE = re.compile(r"^(education)\s*:?\s*$", re.I)
EXPERIENCE_HEADER_RE = re.compile(r"^(experience|work experience|employment)\s*:?\s*$", re.I)
DEGREE_RE = re.compile(
    r"\b("
    r"B\.?\s*S\.?|B\.?\s*A\.?|B\.?\s*E\.?|B\.?\s*Tech|M\.?\s*S\.?|M\.?\s*A\.?|M\.?\s*E\.?|"
    r"Ph\.?\s*D\.?|Bachelor(?:'s)?(?:\s+of\s+Science)?|Master(?:'s)?(?:\s+of\s+Science)?|"
    r"Doctor(?:ate)?(?:\s+of\s+Philosophy)?"
    r")\b",
    re.I,
)
INSTITUTION_HINT_RE = re.compile(
    r"\b(University|College|Institute|School|Academy|Polytechnic)\b",
    re.I,
)


def _extract_text(path: Path) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:
        raise PDFParseError(f"failed to read PDF {path}: {exc}") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise PDFParseError(f"no extractable text in PDF: {path}")
    return text


def _all_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for match in pattern.finditer(text):
        value = match.group(0).strip()
        key = value.lower()
        if key not in seen:
            seen.add(key)
            results.append(value)
    return results


def _guess_name(lines: list[str]) -> str | None:
    for line in lines[:8]:
        candidate = line.strip()
        if not candidate:
            continue
        if EMAIL_RE.search(candidate) or PHONE_RE.search(candidate):
            continue
        if len(candidate.split()) <= 5 and re.match(r"^[A-Za-z][A-Za-z\s'.-]+$", candidate):
            return candidate
    return None


def _section_lines(text: str, header_pattern: re.Pattern[str]) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    collecting = False
    section: list[str] = []
    for line in lines:
        if header_pattern.match(line):
            collecting = True
            continue
        if collecting:
            if line and SECTION_BREAK_RE.match(line) and not header_pattern.match(line):
                break
            if line:
                section.append(line)
    return section


def _looks_like_job_header(line: str) -> bool:
    if DATE_RANGE_RE.search(line):
        return False
    if "|" in line or re.search(r"\s+at\s+", line, re.I):
        return True
    if " - " in line and not INSTITUTION_HINT_RE.search(line):
        left, right = line.split(" - ", 1)
        return bool(left.strip() and right.strip() and len(right.split()) <= 6)
    return False


def _split_experience_blocks(lines: list[str]) -> list[list[str]]:
    """Group experience lines into job blocks, including when blank lines are lost."""
    blocks: list[list[str]] = []
    current: list[str] = []
    saw_date_in_current = False

    for line in lines:
        is_date = bool(DATE_RANGE_RE.search(line))
        is_header = _looks_like_job_header(line)

        if is_header and saw_date_in_current and current:
            blocks.append(current)
            current = [line]
            saw_date_in_current = False
            continue

        current.append(line)
        if is_date:
            saw_date_in_current = True

    if current:
        blocks.append(current)
    return blocks


def _parse_title_company(header: str) -> tuple[str | None, str | None]:
    text = header.strip()
    if not text:
        return None, None
    for sep in ("|", " at ", " @ ", " - "):
        if sep.lower() in text.lower() and sep != " - ":
            parts = re.split(re.escape(sep), text, maxsplit=1, flags=re.I)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None
    if " - " in text:
        left, right = text.split(" - ", 1)
        if INSTITUTION_HINT_RE.search(right):
            return text, None
        return left.strip(), right.strip()
    return text, None


def _parse_experience_block(lines: list[str]) -> ExperienceEntry | None:
    date_idx = next((i for i, line in enumerate(lines) if DATE_RANGE_RE.search(line)), None)
    if date_idx is None:
        return None

    date_line = lines[date_idx]
    date_match = DATE_RANGE_RE.search(date_line)
    start_date = date_match.group("start") if date_match else None
    end_date = date_match.group("end") if date_match else None

    header_lines = [line for line in lines[:date_idx] if line and not DATE_RANGE_RE.search(line)]
    summary_lines = [
        line
        for line in lines[date_idx + 1 :]
        if line and not DATE_RANGE_RE.search(line) and not SECTION_BREAK_RE.match(line)
    ]

    title, company = None, None
    if header_lines:
        title, company = _parse_title_company(header_lines[0])
        if len(header_lines) > 1 and not company:
            company = header_lines[1]

    summary = " ".join(summary_lines).strip() or None
    return ExperienceEntry(
        title=title,
        company=company,
        start_date=start_date,
        end_date=end_date,
        summary=summary,
    )


def _parse_experience(text: str) -> list[ExperienceEntry]:
    section = _section_lines(text, EXPERIENCE_HEADER_RE)
    entries: list[ExperienceEntry] = []
    for block in _split_experience_blocks(section):
        entry = _parse_experience_block(block)
        if entry and (entry.title or entry.company or entry.start_date):
            entries.append(entry)
    return entries


def _parse_education_line(line: str) -> EducationEntry:
    year_match = re.search(r"\b((?:19|20)\d{2})\b", line)
    graduation_date = year_match.group(1) if year_match else None

    degree_match = DEGREE_RE.search(line)
    degree = degree_match.group(0).strip() if degree_match else None

    field: str | None = None
    field_patterns = [
        r"(?:B\.?\s*S\.?|B\.?\s*A\.?|M\.?\s*S\.?|Bachelor(?:'s)?|Master(?:'s)?)"
        r"\s+(?:in|of)\s+([^,]+)",
        r"(?:Major|Field)\s*:\s*([^,|]+)",
    ]
    for pattern in field_patterns:
        match = re.search(pattern, line, re.I)
        if match:
            field = match.group(1).strip()
            break

    if degree and not field:
        trailing = line[degree_match.end() :].strip(" ,.-") if degree_match else ""
        if trailing and not INSTITUTION_HINT_RE.search(trailing.split(",")[0]):
            first_segment = trailing.split(",")[0].strip()
            if first_segment and first_segment != degree:
                field = first_segment

    institution: str | None = None
    parts = [part.strip() for part in line.split(",") if part.strip()]
    institution_candidates = [part for part in parts if INSTITUTION_HINT_RE.search(part)]
    if institution_candidates:
        institution = institution_candidates[-1]
    elif len(parts) >= 2:
        middle = parts[1:-1] if year_match else parts[1:]
        if middle:
            institution = middle[-1]
        elif len(parts) == 2:
            institution = parts[1]

    if institution and year_match and institution.endswith(year_match.group(1)):
        institution = institution[: -len(year_match.group(1))].strip(" ,")

    return EducationEntry(
        institution=institution,
        degree=degree,
        field=field,
        graduation_date=graduation_date,
    )


def _parse_education(text: str) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    for line in _section_lines(text, EDUCATION_HEADER_RE):
        entry = _parse_education_line(line)
        if entry.institution or entry.degree or entry.field:
            entries.append(entry)
    return entries


def _parse_skills(text: str) -> list[str]:
    section = _section_lines(text, SKILLS_HEADER_RE)
    if section:
        joined = ", ".join(section)
        return [item.strip() for item in re.split(r"[,;|•·]", joined) if item.strip()]
    inline = re.search(r"skills\s*:\s*(.+)$", text, re.I | re.M)
    if inline:
        return [item.strip() for item in re.split(r"[,;|]", inline.group(1)) if item.strip()]
    return []


def _contact_field(
    name: str,
    raw: str,
    *,
    confidence: float,
    index: int,
) -> FieldValue:
    return FieldValue(
        value=raw,
        confidence=confidence,
        provenance=[
            Provenance(
                source=SourceType.RESUME_PDF,
                raw_value=raw,
                extractor="pdf_parser.parse_resume_pdf",
                field_path=f"{name}[{index}]",
            )
        ],
    )


def _field(
    name: str,
    raw: str | None,
    *,
    confidence: float,
) -> FieldValue | None:
    if not raw:
        return None
    return FieldValue(
        value=raw,
        confidence=confidence,
        provenance=[
            Provenance(
                source=SourceType.RESUME_PDF,
                raw_value=raw,
                extractor="pdf_parser.parse_resume_pdf",
                field_path=name,
            )
        ],
    )


def parse_resume_pdf(path: str | Path) -> ParsedProfile:
    """
    Parse resume PDF using text extraction and lightweight heuristics.

    Assumptions:
      - Resume text is machine-readable (not a scanned image).
      - Common US-style section headers and date formats are used.
    """
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise PDFParseError(f"PDF file not found: {pdf_path}")

    text = _extract_text(pdf_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    scorer = Scorer()
    profile = ParsedProfile(source=SourceType.RESUME_PDF)

    name = _guess_name(lines)
    emails = _all_matches(EMAIL_RE, text)
    phones = _all_matches(PHONE_RE, text)
    linkedin = _all_matches(LINKEDIN_RE, text)
    github = _all_matches(GITHUB_RE, text)

    profile.emails = [
        _contact_field("emails", email, confidence=scorer.pdf_email_confidence(email), index=i)
        for i, email in enumerate(emails)
    ]
    profile.phones = [
        _contact_field("phones", phone, confidence=scorer.pdf_phone_confidence(phone), index=i)
        for i, phone in enumerate(phones)
    ]

    if name:
        profile.fields["full_name"] = _field("full_name", name, confidence=scorer.pdf_name_confidence(name))
        parts = name.split()
        if len(parts) >= 2:
            profile.fields["first_name"] = _field("first_name", parts[0], confidence=scorer.pdf_name_confidence(name))
            profile.fields["last_name"] = _field("last_name", parts[-1], confidence=scorer.pdf_name_confidence(name))

    if linkedin:
        profile.fields["linkedin_url"] = _field("linkedin_url", linkedin[0], confidence=scorer.pdf_url_confidence(linkedin[0]))
    if github:
        profile.fields["github_url"] = _field("github_url", github[0], confidence=scorer.pdf_url_confidence(github[0]))

    for line in lines[1:6]:
        location = extract_location_from_header(line)
        if location:
            profile.fields["location"] = _field("location", location, confidence=0.7)
            break

    profile.skills = _parse_skills(text)
    profile.skill_confidence = scorer.pdf_skills_confidence(profile.skills)
    profile.experience = _parse_experience(text)
    profile.experience_confidence = scorer.pdf_experience_confidence(profile.experience)
    profile.education = _parse_education(text)
    profile.education_confidence = scorer.pdf_education_confidence(profile.education)

    if profile.experience:
        latest = profile.experience[0]
        if latest.title:
            profile.fields["current_title"] = _field(
                "current_title", latest.title, confidence=profile.experience_confidence
            )
        if latest.company:
            profile.fields["current_company"] = _field(
                "current_company", latest.company, confidence=profile.experience_confidence
            )

    summary_lines: list[str] = []
    for line in lines[1:12]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line):
            continue
        if EXPERIENCE_HEADER_RE.match(line) or SKILLS_HEADER_RE.match(line) or EDUCATION_HEADER_RE.match(line):
            break
        if line.upper() == "SUMMARY":
            continue
        if len(line) > 35:
            summary_lines.append(line)
    if summary_lines:
        profile.fields["summary"] = _field("summary", " ".join(summary_lines[:2]), confidence=0.55)

    return profile
