"""Minimal PDF write/read helpers that do not require PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path: str | Path, lines: list[str], title: str = "Resume") -> Path:
    """Write a single-page Helvetica PDF from plain-text lines."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    content_lines = ["BT", "/F1 11 Tf", "14 TL", "72 760 Td"]
    first = True
    for raw in lines:
        line = (raw or "").replace("\t", "    ")
        if len(line) > 110:
            line = line[:107] + "..."
        escaped = escape_pdf_text(line)
        if first:
            content_lines.append(f"({escaped}) Tj")
            first = False
        else:
            content_lines.append("T*")
            content_lines.append(f"({escaped}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = []

    def add(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    add(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
    )
    add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    add(b"<< /Title (%s) /Producer (hiring-agent) >>" % escape_pdf_text(title).encode("latin-1", errors="replace"))

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(payload)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    dest.write_bytes(bytes(out))
    return dest


_Tj_RE = re.compile(r"\((?:\\.|[^\\)])*\)\s*Tj")
_LITERAL_RE = re.compile(r"\\(.)")


def extract_text_from_simple_pdf(data: bytes) -> str:
    """Pull text from uncompressed `(...) Tj` operators, used by write_simple_pdf."""
    pieces: list[str] = []
    for match in _Tj_RE.finditer(data.decode("latin-1", errors="replace")):
        inner = match.group(0)
        inner = inner[1 : inner.rfind(")")]
        inner = _LITERAL_RE.sub(r"\1", inner)
        pieces.append(inner)
    return "\n".join(pieces)


def load_resume_text(path: str | Path, raw: bytes | None = None) -> str:
    """Load resume text from markdown/plain files or a simple PDF."""
    dest = Path(path)
    suffix = dest.suffix.lower()
    payload = raw if raw is not None else dest.read_bytes()

    if suffix in {".md", ".txt", ".text"}:
        return payload.decode("utf-8", errors="replace")

    if suffix == ".pdf":
        try:
            import pymupdf  # type: ignore

            with pymupdf.open(stream=payload, filetype="pdf") as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception:
            text = extract_text_from_simple_pdf(payload)
            if text.strip():
                return text
            raise ValueError(
                "Could not read this PDF. Save the resume as .md/.txt, or install PyMuPDF."
            )

    return payload.decode("utf-8", errors="replace")
