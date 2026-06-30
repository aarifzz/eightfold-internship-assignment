"""Generate a sample resume PDF for demos and tests."""

from __future__ import annotations

from pathlib import Path


RESUME_LINES = [
    "Jane Doe",
    "Senior Software Engineer | San Francisco, CA",
    "jane.doe@work-email.com | (415) 555-0101",
    "https://linkedin.com/in/janedoe",
    "https://github.com/janedoe",
    "",
    "SUMMARY",
    "Backend engineer with 7+ years building distributed systems in Python and cloud-native stacks.",
    "",
    "EXPERIENCE",
    "Senior Software Engineer | Acme Corp",
    "Jan 2022 - Present",
    "Built APIs and data pipelines using Python, AWS, and Kubernetes.",
    "",
    "Software Engineer | Beta Labs",
    "Jun 2018 - Dec 2021",
    "Developed microservices with JavaScript, Node.js, and PostgreSQL.",
    "",
    "EDUCATION",
    "B.S. Computer Science, State University, 2018",
    "",
    "SKILLS",
    "Python, JavaScript, TypeScript, AWS, Kubernetes, PostgreSQL, Docker",
]


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(lines: list[str], output_path: Path) -> None:
    """
    Write a minimal text-only PDF without third-party dependencies.

    Assumes Latin-1 encodable content suitable for sample resumes.
    """
    y_start = 780
    line_height = 14
    content_lines = ["BT", "/F1 11 Tf", f"50 {y_start} Td"]
    for index, line in enumerate(lines):
        if index > 0:
            content_lines.append(f"0 -{line_height} Td")
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        b"4 0 obj<< /Length " + str(len(stream)).encode() + b" >>stream\n" + stream + b"\nendstream endobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        handle.write(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(handle.tell())
            handle.write(obj)
        xref_offset = handle.tell()
        handle.write(f"xref\n0 {len(offsets)}\n".encode())
        handle.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            handle.write(f"{offset:010d} 00000 n \n".encode())
        handle.write(
            f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
        )


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "samples" / "resume.pdf"
    write_simple_pdf(RESUME_LINES, target)
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
