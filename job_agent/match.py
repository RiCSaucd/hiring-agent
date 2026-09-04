"""Fit scoring between a parsed resume and a job listing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from job_agent.parser import ParsedResume, resume_plain_text
from job_agent.search import Job
from job_agent.skills import extract_skills, skill_overlap, tokenize


@dataclass
class JobFit:
    job_id: str
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    reasons: list[str]
    risks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "score": self.score,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "reasons": self.reasons,
            "risks": self.risks,
        }


def score_fit(resume: ParsedResume, job: Job, target_role: str = "") -> JobFit:
    resume_skills = resume.skills or extract_skills(resume_plain_text(resume))
    job_skills = extract_skills(f"{job.title} {job.description} {' '.join(job.tags)}")
    if job.tags:
        for tag in job.tags:
            if tag not in job_skills:
                job_skills.append(tag)
    matched, missing = skill_overlap(resume_skills, job_skills)

    resume_tokens = tokenize(resume_plain_text(resume) + " " + target_role)
    title_tokens = tokenize(job.title)
    desc_tokens = tokenize(job.description)
    title_hits = title_tokens & resume_tokens
    desc_hits = desc_tokens & resume_tokens

    skill_score = 0 if not job_skills else int(70 * len(matched) / max(1, len(set(job_skills) | set(matched))))
    title_score = 0 if not title_tokens else int(20 * len(title_hits) / len(title_tokens))
    desc_score = 0 if not desc_tokens else int(10 * min(1.0, len(desc_hits) / 12))
    total = max(0, min(100, skill_score + title_score + desc_score))

    reasons: list[str] = []
    risks: list[str] = []
    if matched:
        reasons.append(" overlapping skills: " + ", ".join(matched[:8]))
        reasons[-1] = "Overlapping skills: " + ", ".join(matched[:8])
    if title_hits:
        reasons.append("Title keywords you already use: " + ", ".join(sorted(title_hits)[:6]))
    if job.remote:
        reasons.append("Remote-friendly listing — location friction is low.")
    if missing:
        risks.append("Not explicit on the resume: " + ", ".join(missing[:8]))
    if total < 40:
        risks.append("Low keyword overlap — tailor bullets before applying.")
    if not reasons:
        reasons.append("Limited direct overlap; treat this as a stretch listing.")

    return JobFit(
        job_id=job.id,
        score=total,
        matched_skills=matched,
        missing_skills=missing[:12],
        reasons=reasons,
        risks=risks,
    )


def rank_jobs(resume: ParsedResume, jobs: list[Job], target_role: str = "") -> list[tuple[Job, JobFit]]:
    ranked = [(job, score_fit(resume, job, target_role=target_role)) for job in jobs]
    ranked.sort(key=lambda pair: pair[1].score, reverse=True)
    return ranked
