"""Job listings: bundled catalog plus optional live public APIs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

from job_agent.skills import extract_skills, tokenize

DATA_DIR = Path(__file__).resolve().parent / "data"
CATALOG_PATH = DATA_DIR / "jobs.json"

USER_AGENT = "hiring-agent-jobseeker/0.2 (+https://github.com/RiCSaucd/hiring-agent)"


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    remote: bool
    url: str
    apply_url: str
    description: str
    tags: list[str]
    seniority: str = "mid"
    source: str = "catalog"
    how_to_apply: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "remote": self.remote,
            "url": self.url,
            "apply_url": self.apply_url,
            "description": self.description,
            "tags": self.tags,
            "seniority": self.seniority,
            "source": self.source,
            "how_to_apply": self.how_to_apply,
            "skills": extract_skills(self.title + " " + self.description + " " + " ".join(self.tags)),
        }


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "job"


def job_from_dict(payload: dict[str, Any], source: str | None = None) -> Job:
    title = str(payload.get("title") or "Untitled role")
    company = str(payload.get("company") or payload.get("company_name") or "Unknown")
    job_id = str(payload.get("id") or f"{_slug(company)}-{_slug(title)}")
    description = str(payload.get("description") or payload.get("description_text") or "")
    tags = payload.get("tags") or payload.get("category") or []
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    location = str(payload.get("location") or payload.get("candidate_required_location") or "")
    remote = bool(payload.get("remote", "remote" in location.lower() or payload.get("candidate_required_location") == "Worldwide"))
    url = str(payload.get("url") or payload.get("url") or payload.get("apply_url") or "")
    apply_url = str(payload.get("apply_url") or url)
    return Job(
        id=job_id,
        title=title,
        company=company,
        location=location or ("Remote" if remote else ""),
        remote=remote,
        url=url,
        apply_url=apply_url,
        description=description,
        tags=[str(tag).lower() for tag in tags],
        seniority=str(payload.get("seniority") or "mid"),
        source=source or str(payload.get("source") or "catalog"),
        how_to_apply=str(payload.get("how_to_apply") or "Open the apply URL and paste the generated packet."),
    )


def load_catalog(path: Path | None = None) -> list[Job]:
    catalog = Path(path) if path else CATALOG_PATH
    raw = json.loads(catalog.read_text(encoding="utf-8"))
    return [job_from_dict(item, source="catalog") for item in raw]


def _http_json(url: str, timeout: int = 12) -> Any | None:
    try:
        import requests
    except ImportError:
        return None
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None


def fetch_live_jobs(query: str = "", limit: int = 20) -> tuple[list[Job], list[str]]:
    """Best-effort live fetch. Returns (jobs, skipped_sources)."""
    jobs: list[Job] = []
    skipped: list[str] = []
    encoded = urlencode({"search": query, "limit": str(limit)}) if query else f"limit={limit}"

    remotive = _http_json(f"https://remotive.com/api/remote-jobs?{encoded}")
    if remotive and isinstance(remotive, dict):
        for item in (remotive.get("jobs") or [])[:limit]:
            jobs.append(
                job_from_dict(
                    {
                        "id": f"remotive-{item.get('id')}",
                        "title": item.get("title"),
                        "company": item.get("company_name"),
                        "location": item.get("candidate_required_location"),
                        "url": item.get("url"),
                        "apply_url": item.get("url"),
                        "description": item.get("description"),
                        "tags": item.get("tags") or [],
                        "remote": True,
                    },
                    source="remotive",
                )
            )
    else:
        skipped.append("remotive")

    jobicy_q = urlencode({"count": str(min(limit, 20)), "tag": query}) if query else "count=10"
    jobicy = _http_json(f"https://jobicy.com/api/v2/remote-jobs?{jobicy_q}")
    if jobicy and isinstance(jobicy, dict):
        for item in (jobicy.get("jobs") or [])[:limit]:
            jobs.append(
                job_from_dict(
                    {
                        "id": f"jobicy-{item.get('id')}",
                        "title": item.get("jobTitle"),
                        "company": item.get("companyName"),
                        "location": item.get("jobGeo"),
                        "url": item.get("url"),
                        "apply_url": item.get("url"),
                        "description": item.get("jobDescription"),
                        "tags": item.get("jobIndustry") or [],
                        "remote": True,
                    },
                    source="jobicy",
                )
            )
    else:
        skipped.append("jobicy")

    arbeitnow = _http_json("https://www.arbeitnow.com/api/job-board-api")
    if arbeitnow and isinstance(arbeitnow, dict):
        needle = query.lower()
        for item in arbeitnow.get("data") or []:
            blob = f"{item.get('title', '')} {item.get('description', '')}".lower()
            if needle and needle not in blob:
                continue
            jobs.append(
                job_from_dict(
                    {
                        "id": f"arbeitnow-{_slug(str(item.get('slug') or item.get('title')))}",
                        "title": item.get("title"),
                        "company": item.get("company_name"),
                        "location": item.get("location"),
                        "url": item.get("url"),
                        "apply_url": item.get("url"),
                        "description": item.get("description"),
                        "tags": item.get("tags") or [],
                        "remote": bool(item.get("remote")),
                    },
                    source="arbeitnow",
                )
            )
            if len([job for job in jobs if job.source == "arbeitnow"]) >= limit:
                break
    else:
        skipped.append("arbeitnow")

    return jobs, skipped


def filter_jobs(
    jobs: Iterable[Job],
    query: str = "",
    remote_only: bool = False,
    location: str = "",
) -> list[Job]:
    query_tokens = tokenize(query)
    location_l = location.lower().strip()
    results: list[Job] = []
    for job in jobs:
        if remote_only and not job.remote:
            continue
        if location_l and location_l not in job.location.lower() and not (job.remote and location_l in {"remote", "anywhere"}):
            continue
        if query_tokens:
            hay = tokenize(f"{job.title} {job.company} {job.description} {' '.join(job.tags)}")
            if not query_tokens.issubset(hay) and not (query_tokens & hay):
                continue
        results.append(job)
    return results


def search_jobs(
    query: str = "",
    remote_only: bool = False,
    location: str = "",
    include_live: bool = True,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    catalog = load_catalog(catalog_path)
    live: list[Job] = []
    skipped: list[str] = []
    if include_live:
        live, skipped = fetch_live_jobs(query=query)
    combined: dict[str, Job] = {}
    for job in list(live) + catalog:
        combined.setdefault(job.id, job)
    filtered = filter_jobs(combined.values(), query=query, remote_only=remote_only, location=location)
    return {
        "jobs": [job.to_dict() for job in filtered],
        "count": len(filtered),
        "live_count": len(live),
        "skipped_sources": skipped,
        "catalog_count": len(catalog),
    }
