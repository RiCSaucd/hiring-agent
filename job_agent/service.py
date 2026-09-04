"""Orchestration for review, search, match, and apply."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from job_agent.match import JobFit, rank_jobs, score_fit
from job_agent.materials import build_packet
from job_agent.parser import ParsedResume, parse_resume_text
from job_agent.pdfutil import load_resume_text
from job_agent.review import review_application
from job_agent.search import Job, job_from_dict, load_catalog, search_jobs
from job_agent.tracker import Tracker

DEFAULT_DB = Path("var") / "hiring_agent.db"


class HiringDesk:
    def __init__(self, db_path: str | Path = DEFAULT_DB, catalog_path: Path | None = None):
        self.tracker = Tracker(db_path)
        self.catalog_path = catalog_path
        self._jobs_by_id: dict[str, Job] = {}
        for job in load_catalog(catalog_path):
            self._remember_job(job)

    def close(self) -> None:
        self.tracker.close()

    def _remember_job(self, job: Job) -> None:
        self._jobs_by_id[job.id] = job
        self.tracker.upsert_job(job.to_dict())

    def _parsed_from_profile(self) -> ParsedResume:
        profile = self.tracker.get_profile()
        if not profile["has_resume"]:
            raise ValueError("Upload a resume before doing that.")
        return _resume_from_stored(profile["resume"], profile.get("resume_filename") or "")

    def ingest_resume_bytes(
        self,
        filename: str,
        payload: bytes,
        target_role: str = "",
        target_location: str = "",
        remote_only: bool | None = None,
    ) -> dict[str, Any]:
        text = load_resume_text(filename, raw=payload)
        return self.ingest_resume_text(
            filename=filename,
            text=text,
            target_role=target_role,
            target_location=target_location,
            remote_only=remote_only,
        )

    def ingest_resume_text(
        self,
        filename: str,
        text: str,
        target_role: str = "",
        target_location: str = "",
        remote_only: bool | None = None,
    ) -> dict[str, Any]:
        parsed = parse_resume_text(text, filename=filename)
        profile = self.tracker.save_resume(
            resume=parsed.to_dict(),
            resume_text=text,
            filename=filename,
            target_role=target_role or None,
            target_location=target_location or None,
            remote_only=remote_only,
        )
        review = review_application(parsed, target_role=profile["target_role"])
        return {"profile": profile, "review": review.to_dict(), "resume": parsed.to_dict()}

    def ingest_resume_base64(self, filename: str, content_b64: str, **kwargs: Any) -> dict[str, Any]:
        payload = base64.b64decode(content_b64)
        return self.ingest_resume_bytes(filename, payload, **kwargs)

    def set_preferences(self, **kwargs: Any) -> dict[str, Any]:
        return self.tracker.update_preferences(**kwargs)

    def review(self, target_role: str | None = None) -> dict[str, Any]:
        if target_role is not None:
            self.tracker.update_preferences(target_role=target_role)
        profile = self.tracker.get_profile()
        parsed = self._parsed_from_profile()
        review = review_application(parsed, target_role=profile["target_role"])
        return {"profile": profile, "review": review.to_dict(), "resume": parsed.to_dict()}

    def search(
        self,
        query: str = "",
        include_live: bool = True,
        remote_only: bool | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        profile = self.tracker.get_profile()
        role_query = query or profile["target_role"]
        remote = profile["remote_only"] if remote_only is None else remote_only
        loc = profile["target_location"] if location is None else location
        result = search_jobs(
            query=role_query,
            remote_only=remote,
            location=loc,
            include_live=include_live,
            catalog_path=self.catalog_path,
        )
        parsed = None
        try:
            parsed = self._parsed_from_profile()
        except ValueError:
            parsed = None
        ranked: list[dict[str, Any]] = []
        for item in result["jobs"]:
            job = job_from_dict(item, source=item.get("source"))
            self._remember_job(job)
            entry = dict(item)
            if parsed is not None:
                fit = score_fit(parsed, job, target_role=profile["target_role"] or role_query)
                entry["fit"] = fit.to_dict()
            ranked.append(entry)
        ranked.sort(key=lambda row: (row.get("fit") or {}).get("score") or 0, reverse=True)
        result["jobs"] = ranked
        result["query"] = role_query
        return result

    def paste_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        job = job_from_dict(payload, source=payload.get("source") or "pasted")
        self._remember_job(job)
        profile = self.tracker.get_profile()
        fit = None
        if profile["has_resume"]:
            fit = score_fit(self._parsed_from_profile(), job, target_role=profile["target_role"]).to_dict()
        return {"job": job.to_dict(), "fit": fit}

    def get_job(self, job_id: str) -> Job:
        cached = self._jobs_by_id.get(job_id)
        if cached:
            return cached
        stored = self.tracker.get_job(job_id)
        if not stored:
            raise KeyError(f"Unknown job {job_id}")
        job = job_from_dict(stored, source=stored.get("source"))
        self._jobs_by_id[job.id] = job
        return job

    def fit(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        parsed = self._parsed_from_profile()
        profile = self.tracker.get_profile()
        fit = score_fit(parsed, job, target_role=profile["target_role"])
        return {"job": job.to_dict(), "fit": fit.to_dict()}

    def prepare(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        parsed = self._parsed_from_profile()
        profile = self.tracker.get_profile()
        fit: JobFit = score_fit(parsed, job, target_role=profile["target_role"])
        packet = build_packet(parsed, job, fit)
        application = self.tracker.create_application(job.id, packet.to_dict(), fit.to_dict())
        return application

    def apply(self, application_id: int, confirm: bool, notes: str = "") -> dict[str, Any]:
        return self.tracker.mark_applied(application_id, confirm=confirm, notes=notes)

    def applications(self) -> list[dict[str, Any]]:
        return self.tracker.list_applications()

    def status(self) -> dict[str, Any]:
        profile = self.tracker.get_profile()
        return {
            "profile": profile,
            "applications": self.applications(),
            "job_count": len(self._jobs_by_id),
        }


def _resume_from_stored(payload: dict[str, Any], filename: str) -> ParsedResume:
    from job_agent.parser import ProjectEntry, WorkEntry

    experience = [
        WorkEntry(
            raw=item.get("raw") or "",
            organization=item.get("organization") or "",
            title=item.get("title") or "",
            dates=item.get("dates") or "",
            highlights=list(item.get("highlights") or []),
        )
        for item in payload.get("experience") or []
    ]
    projects = [
        ProjectEntry(
            name=item.get("name") or "",
            description=item.get("description") or "",
            url=item.get("url") or "",
        )
        for item in payload.get("projects") or []
    ]
    return ParsedResume(
        name=payload.get("name") or "",
        email=payload.get("email") or "",
        phone=payload.get("phone") or "",
        location=payload.get("location") or "",
        summary=payload.get("summary") or "",
        skills=list(payload.get("skills") or []),
        experience=experience,
        education=list(payload.get("education") or []),
        projects=projects,
        urls=list(payload.get("urls") or []),
        github=payload.get("github") or "",
        linkedin=payload.get("linkedin") or "",
        raw_text=payload.get("raw_text") or "",
        word_count=int(payload.get("word_count") or 0),
        source_filename=payload.get("source_filename") or filename,
    )
