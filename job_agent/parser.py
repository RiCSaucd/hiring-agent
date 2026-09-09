"""Heuristic resume parser — works without an LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from job_agent.skills import extract_skills

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]?\d{4}")
URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)
HEADING_RE = re.compile(
    r"^(?:"
    r"(?:professional\s+)?summary|profile|about(?: me)?|"
    r"(?:professional\s+|relevant\s+)?experience|work(?: experience)?|employment|"
    r"education|academics|"
    r"(?:core\s+|technical\s+(?:and|&)\s+professional\s+)?skills|technical skills|technologies|"
    r"projects|selected projects|"
    r"awards|achievements|"
    r"certifications?(?:\s+(?:and|&)\s+licenses?)?|certificates|"
    r"licenses?|"
    r"languages?"
    r")\s*:?\s*$",
    re.IGNORECASE,
)
SECTION_ALIASES = {
    "summary": "summary",
    "professional summary": "summary",
    "profile": "summary",
    "about": "summary",
    "about me": "summary",
    "experience": "experience",
    "professional experience": "experience",
    "relevant experience": "experience",
    "work": "experience",
    "work experience": "experience",
    "employment": "experience",
    "education": "education",
    "academics": "education",
    "skills": "skills",
    "core skills": "skills",
    "technical skills": "skills",
    "technical and professional skills": "skills",
    "technical & professional skills": "skills",
    "technologies": "skills",
    "projects": "projects",
    "selected projects": "projects",
    "awards": "awards",
    "achievements": "awards",
    "certification": "awards",
    "certifications": "awards",
    "certifications and licenses": "awards",
    "certifications & licenses": "awards",
    "certificates": "awards",
    "licenses": "awards",
    "license": "awards",
    "language": "awards",
    "languages": "awards",
}
ACTION_VERBS = (
    "led",
    "built",
    "designed",
    "implemented",
    "launched",
    "reduced",
    "increased",
    "owned",
    "created",
    "improved",
    "migrated",
    "automated",
    "shipped",
    "developed",
    "architected",
    "scaled",
    "cut",
    "delivered",
    "audited",
    "documented",
    "mapped",
    "managed",
    "maintained",
    "applied",
    "deployed",
    "identified",
    "rebuilt",
    "wrote",
    "promoted",
    "analyzed",
    "coordinated",
    "negotiated",
    "reconciled",
    "streamlined",
    "tracked",
    "supported",
    "optimized",
    "ensured",
    "partnered",
    "conducted",
)


@dataclass
class WorkEntry:
    raw: str
    organization: str = ""
    title: str = ""
    dates: str = ""
    highlights: list[str] = field(default_factory=list)


@dataclass
class ProjectEntry:
    name: str
    description: str = ""
    url: str = ""


@dataclass
class ParsedResume:
    name: str
    email: str
    phone: str
    location: str
    summary: str
    skills: list[str]
    experience: list[WorkEntry]
    education: list[str]
    projects: list[ProjectEntry]
    urls: list[str]
    github: str
    linkedin: str
    raw_text: str
    word_count: int
    source_filename: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "summary": self.summary,
            "skills": self.skills,
            "experience": [
                {
                    "raw": item.raw,
                    "organization": item.organization,
                    "title": item.title,
                    "dates": item.dates,
                    "highlights": item.highlights,
                }
                for item in self.experience
            ],
            "education": self.education,
            "projects": [
                {"name": item.name, "description": item.description, "url": item.url}
                for item in self.projects
            ],
            "urls": self.urls,
            "github": self.github,
            "linkedin": self.linkedin,
            "word_count": self.word_count,
            "source_filename": self.source_filename,
        }


def _format_phone(raw: str) -> str:
    """Normalize a US-style number so the dossier shows a readable phone."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return (raw or "").strip()


def _clean_lines(text: str) -> list[str]:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    return [line for line in lines if line]


def _heading_key(line: str) -> str | None:
    """Map a short heading line to a resume section, including 'Professional Summary'."""
    if re.match(r"^[\-•*]\s+", line):
        return None
    stripped = line.strip(" -:•")
    cleaned = re.sub(r"[^a-z& ]+", " ", stripped.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned or len(cleaned.split()) > 8:
        return None
    if cleaned in SECTION_ALIASES:
        return SECTION_ALIASES[cleaned]
    if HEADING_RE.match(stripped):
        return SECTION_ALIASES.get(cleaned)
    return None


def _sectionize(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        key = _heading_key(line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _guess_name(header_lines: list[str], email: str) -> str:
    skip = {email.lower()} if email else set()
    for line in header_lines[:6]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
            continue
        if line.lower() in skip:
            continue
        if 2 <= len(line.split()) <= 5 and not _heading_key(line):
            if any(ch.isdigit() for ch in line):
                continue
            return line
    return header_lines[0] if header_lines else "Candidate"


def _guess_location(header_lines: list[str]) -> str:
    parts: list[str] = []
    for line in header_lines:
        parts.extend(bit.strip() for bit in re.split(r"\s*\|\s*", line) if bit.strip())
    city_state = re.compile(
        r"([A-Z][A-Za-z. ]+,\s*(?:[A-Z]{2}|Florida|Georgia|California|Texas|"
        r"New York|North Carolina|South Carolina|Panama|Panam[aá])(?:\s+\d{5})?)"
    )
    for part in parts:
        if EMAIL_RE.search(part) or URL_RE.search(part) or PHONE_RE.search(part):
            continue
        if re.search(r"bilingual", part, re.I):
            continue
        match = city_state.search(part)
        if match:
            return match.group(1).strip()
        if re.search(r"\b(remote|united states|usa|uk|canada|germany|india)\b", part, re.I):
            return part
    return ""


def _split_bullets(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    for line in lines:
        cleaned = re.sub(r"^[\-•*]\s*", "", line).strip()
        if cleaned:
            bullets.append(cleaned)
    return bullets


def _parse_experience(lines: list[str]) -> list[WorkEntry]:
    entries: list[WorkEntry] = []
    current: WorkEntry | None = None
    date_re = re.compile(
        r"((?:\d{1,2}/)?(?:19|20)\d{2}|"
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b)"
        r".{0,24}(present|(?:\d{1,2}/)?(?:19|20)\d{2})",
        re.IGNORECASE,
    )
    date_only_re = re.compile(
        r"^(?:\d{1,2}/\d{4}|(?:19|20)\d{2}|"
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{4})"
        r"\s*[–\-]\s*"
        r"(?:present|\d{1,2}/\d{4}|(?:19|20)\d{2}|"
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{4})\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        is_bullet = bool(re.match(r"^[\-•*]\s+", line))
        if not is_bullet and current is not None and date_only_re.match(line):
            current.dates = date_only_re.match(line).group(0)
            continue
        if not is_bullet and (date_re.search(line) or " — " in line or " - " in line or " at " in line.lower()):
            if current:
                entries.append(current)
            dates = date_re.search(line)
            title = ""
            org = ""
            if " — " in line:
                chunks = [part.strip() for part in line.split(" — ")]
                title = chunks[0]
                org = chunks[1] if len(chunks) > 1 else ""
                if org:
                    org = re.split(r"\s+\(", org, maxsplit=1)[0].strip()
                    org = date_re.sub("", org)
                    org = re.sub(r"\(\s*\)", "", org).strip(" ,–-")
            elif " at " in line.lower():
                parts = re.split(r"\bat\b", line, maxsplit=1, flags=re.I)
                title, org = parts[0].strip(" -"), parts[1].strip()
            else:
                title = line
            current = WorkEntry(
                raw=line,
                organization=org,
                title=title,
                dates=dates.group(0) if dates else "",
                highlights=[],
            )
        elif current is not None:
            current.highlights.append(re.sub(r"^[\-•*]\s*", "", line))
        else:
            current = WorkEntry(raw=line, title=line, highlights=[])
    if current:
        entries.append(current)
    return entries


def _parse_projects(lines: list[str]) -> list[ProjectEntry]:
    projects: list[ProjectEntry] = []
    current: ProjectEntry | None = None
    for line in lines:
        is_bullet = bool(re.match(r"^[\-•*]\s+", line))
        url_match = URL_RE.search(line)
        if not is_bullet and not line.startswith("http"):
            if current:
                projects.append(current)
            name = re.sub(r"^[\-•*]\s*", "", line)
            name = re.split(r"\s+[—\-]\s+", name, maxsplit=1)[0]
            current = ProjectEntry(name=name.strip(), description=line, url=url_match.group(0) if url_match else "")
        elif current is not None:
            current.description = (current.description + " " + line).strip()
            if url_match and not current.url:
                current.url = url_match.group(0)
        else:
            current = ProjectEntry(name=line[:80], description=line, url=url_match.group(0) if url_match else "")
    if current:
        projects.append(current)
    return projects


def parse_resume_text(text: str, filename: str = "") -> ParsedResume:
    """Parse unstructured resume text into a structured dossier."""
    if not text or not text.strip():
        raise ValueError("Resume text is empty")

    lines = _clean_lines(text)
    sections = _sectionize(lines)
    header = sections.get("header", [])
    emails = EMAIL_RE.findall(text)
    phones = [_format_phone(match) for match in PHONE_RE.findall(text)]
    urls = URL_RE.findall(text)
    github = next((url for url in urls if "github.com" in url.lower()), "")
    linkedin = next((url for url in urls if "linkedin.com" in url.lower()), "")

    skills_lines = sections.get("skills", [])
    skills = extract_skills(" ".join(skills_lines) + "\n" + text)

    summary = " ".join(sections.get("summary", [])).strip()
    education = _split_bullets(sections.get("education", []))
    if not education:
        education = sections.get("education", [])

    words = re.findall(r"\b\w+\b", text)

    return ParsedResume(
        name=_guess_name(header, emails[0] if emails else ""),
        email=emails[0] if emails else "",
        phone=phones[0] if phones else "",
        location=_guess_location(header),
        summary=summary,
        skills=skills,
        experience=_parse_experience(sections.get("experience", [])),
        education=education,
        projects=_parse_projects(sections.get("projects", [])),
        urls=urls,
        github=github,
        linkedin=linkedin,
        raw_text=text,
        word_count=len(words),
        source_filename=filename,
    )


def resume_plain_text(parsed: ParsedResume) -> str:
    """Flatten a parsed resume for matching and cover letters."""
    parts = [
        parsed.name,
        parsed.summary,
        " ".join(parsed.skills),
        " ".join(item.raw + " " + " ".join(item.highlights) for item in parsed.experience),
        " ".join(item.name + " " + item.description for item in parsed.projects),
        " ".join(parsed.education),
    ]
    return "\n".join(part for part in parts if part)
