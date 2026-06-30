"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eightfold_profile import __version__
from eightfold_profile.pipeline import PipelineError, build_from_paths, write_json_output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eightfold-profile",
        description=(
            "Merge recruiter CSV and resume PDF into a canonical candidate profile "
            "with normalization, confidence-based merging, and schema validation."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--csv",
        required=False,
        type=Path,
        help="Path to recruiter CSV (structured source)",
    )
    parser.add_argument(
        "--pdf",
        required=False,
        type=Path,
        help="Path to candidate resume PDF (unstructured source)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional JSON runtime config for projection and behavior",
    )
    parser.add_argument(
        "--candidate-id",
        default=None,
        help="Candidate ID to select from CSV when multiple rows exist",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write JSON result to file (prints to stdout when omitted)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON to stdout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.csv and not args.pdf:
        print("error: at least one input source (--csv or --pdf) must be provided", file=sys.stderr)
        return 1

    try:
        profile = build_from_paths(
            csv_path=args.csv,
            pdf_path=args.pdf,
            config_path=args.config,
            candidate_id=args.candidate_id,
        )
    except PipelineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130

    if args.output:
        try:
            write_json_output(profile, args.output)
        except OSError as exc:
            print(f"error writing output: {exc}", file=sys.stderr)
            return 1

    if args.output is None or args.pretty:
        indent = 2 if args.pretty or args.output else None
        print(json.dumps(profile, indent=indent, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
