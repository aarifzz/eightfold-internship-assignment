"""End-to-end profile build pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from eightfold_profile.canonical import build_canonical_profile
from eightfold_profile.config import AppConfig, load_config
from eightfold_profile.merging import merge_profiles
from eightfold_profile.models import ParsedProfile, SourceType
from eightfold_profile.normalization import NormalizationError, normalize_profile
from eightfold_profile.parsing import parse_recruiter_csv, parse_resume_pdf
from eightfold_profile.parsing.pdf_parser import PDFParseError
from eightfold_profile.projection import project_profile
from eightfold_profile.validation import validate_output


class PipelineError(RuntimeError):
    """Raised when the profile pipeline cannot complete."""


def _ensure_candidate_id(profile: dict[str, Any]) -> None:
    """Generate deterministic candidate_id if missing (Requirement 8)."""
    if profile.get("candidate_id"):
        return

    # Prefer email
    if profile.get("emails"):
        profile["candidate_id"] = profile["emails"][0]
        return

    # Otherwise full name
    if profile.get("full_name"):
        # Basic normalization for ID: lowercase and hyphens
        name = profile["full_name"].lower().replace(" ", "-")
        profile["candidate_id"] = name


def build_candidate_profile(
    *,
    csv_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    config: AppConfig | None = None,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    """
    Parse, normalize, merge, project, and validate a canonical candidate profile.

    Returns a JSON-serializable dict ready for downstream ATS/talent systems.
    """
    active_config = config or AppConfig()
    parsed_profiles: list[ParsedProfile] = []

    # Attempt CSV parsing if provided
    if csv_path:
        try:
            csv_profile = parse_recruiter_csv(csv_path, candidate_id=candidate_id)
            parsed_profiles.append(csv_profile)
        except (OSError, ValueError) as exc:
            # If CSV is malformed or missing, we continue only if PDF is available
            if not pdf_path:
                raise PipelineError(f"CSV parsing failed: {exc}") from exc

    # Attempt PDF parsing if provided
    if pdf_path:
        try:
            pdf_profile = parse_resume_pdf(pdf_path)
            parsed_profiles.append(pdf_profile)
        except (PDFParseError, OSError, ValueError) as exc:
            # If PDF is malformed or missing, we continue only if CSV is available
            if not csv_path or not parsed_profiles:
                raise PipelineError(f"PDF parsing failed: {exc}") from exc

    if not parsed_profiles:
        raise PipelineError("No valid input sources could be parsed.")

    try:
        normalized_profiles = [
            normalize_profile(p, active_config) for p in parsed_profiles
        ]
    except NormalizationError as exc:
        raise PipelineError(f"normalization failed: {exc}") from exc

    merged = merge_profiles(normalized_profiles)
    canonical = build_canonical_profile(merged, active_config)

    try:
        projected = project_profile(canonical, active_config)
    except ValueError as exc:
        raise PipelineError(f"projection failed: {exc}") from exc

    # Ensure deterministic ID (Requirement 8) before validation
    _ensure_candidate_id(projected)

    try:
        validate_output(projected, config=active_config)
    except ValidationError as exc:
        raise PipelineError(f"validation failed: {exc.message}") from exc

    return projected


def build_from_paths(
    csv_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    config_path: str | Path | None = None,
    *,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    """Convenience wrapper that loads config from disk when provided."""
    config = load_config(config_path)
    return build_candidate_profile(
        csv_path=csv_path,
        pdf_path=pdf_path,
        config=config,
        candidate_id=candidate_id,
    )


def write_json_output(payload: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
