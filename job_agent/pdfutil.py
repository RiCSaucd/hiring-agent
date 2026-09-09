"""Minimal PDF write/read helpers that do not require PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_pdf_lines(lines: list[str], width: int = 96) -> list[str]:
    """Word-wrap plain lines so they fit a letter page."""
    wrapped: list[str] = []
    for raw in lines:
        text = (raw or "").replace("\t", "    ")
        if not text:
            wrapped.append("")
            continue
        while len(text) > width:
            cut = text.rfind(" ", 0, width)
            if cut < width // 3:
                cut = width
            wrapped.append(text[:cut])
            text = text[cut:].lstrip()
        wrapped.append(text)
    return wrapped


def _page_stream(lines: list[str]) -> bytes:
    ops = ["BT", "/F1 10 Tf", "13 TL", "54 740 Td"]
    first = True
    for raw in lines:
        escaped = escape_pdf_text(raw)
        if first:
            ops.append(f"({escaped}) Tj")
            first = False
        else:
            ops.append("T*")
            ops.append(f"({escaped}) Tj")
    if first:
        ops.append("() Tj")
    ops.append("ET")
    return "\n".join(ops).encode("latin-1", errors="replace")


def write_simple_pdf(path: str | Path, lines: list[str], title: str = "Resume") -> Path:
    """Write a Helvetica PDF from plain-text lines, paginating as needed."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wrapped = wrap_pdf_lines(lines)
    chunks = [wrapped[i : i + 46] for i in range(0, max(len(wrapped), 1), 46)]
    streams = [_page_stream(chunk) for chunk in chunks]
    page_count = len(streams)
    font_id = 3 + page_count * 2
    info_id = font_id + 1
    kid_refs = " ".join(f"{3 + i * 2} 0 R" for i in range(page_count))

    objects: list[bytes] = []

    def add(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    add(f"<< /Type /Pages /Kids [{kid_refs}] /Count {page_count} >>".encode("ascii"))
    for index, stream in enumerate(streams):
        page_id = 3 + index * 2
        content_id = page_id + 1
        add(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode("ascii")
        )
        add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    add(
        b"<< /Title (%s) /Producer (hiring-agent) >>"
        % escape_pdf_text(title).encode("latin-1", errors="replace")
    )

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
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R /Info {info_id} 0 R >>\n"
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
