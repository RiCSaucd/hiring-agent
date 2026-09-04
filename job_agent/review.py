"""ATS-style application review with optional LLM scoring."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from job_agent.parser import ACTION_VERBS, ParsedResume, resume_plain_text
from job_agent.skills import extract_skills, skill_overlap


@dataclass
class Finding:
    severity: str  # pass | warn | fail
    code: str
    title: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
        }


@dataclass
class ApplicationReview:
    overall: int
    recruiter_score: int | None
    findings: list[Finding]
    strengths: list[str]
    improvements: list[str]
    target_role: str
    matched_keywords: list[str]
    missing_keywords: list[str]
    llm_used: bool = False
    llm_notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "recruiter_score": self.recruiter_score,
            "findings": [item.to_dict() for item in self.findings],
            "strengths": self.strengths,
            "improvements": self.improvements,
            "target_role": self.target_role,
            "matched_keywords": self.matched_keywords,
            "missing_keywords": self.missing_keywords,
            "llm_used": self.llm_used,
            "llm_notes": self.llm_notes,
        }


def _quantified_bullets(resume: ParsedResume) -> int:
    count = 0
    for job in resume.experience:
        for highlight in job.highlights:
            if re.search(r"\d", highlight):
                count += 1
    return count


def _action_verb_count(resume: ParsedResume) -> int:
    count = 0
    for job in resume.experience:
        for highlight in job.highlights:
            first = highlight.split(" ", 1)[0].lower().strip(".,")
            if first in ACTION_VERBS:
                count += 1
    return count


def review_application(resume: ParsedResume, target_role: str = "") -> ApplicationReview:
    """Score the application packet as a recruiter would, without demographic bias."""
    findings: list[Finding] = []
    strengths: list[str] = []
    improvements: list[str] = []
    score = 40

    if resume.email:
        findings.append(
            Finding("pass", "email", "Contact email", f"Found {resume.email}.")
        )
        score += 8
    else:
        findings.append(
            Finding("fail", "email", "Missing email", "Add a professional email ATS parsers can read.")
        )
        improvements.append("Add a plain-text email in the header.")

    if resume.phone:
        findings.append(Finding("pass", "phone", "Phone number", "Phone number is present."))
        score += 4
    else:
        findings.append(
            Finding("warn", "phone", "No phone number", "Many ATS forms still ask for a phone number.")
        )

    if resume.github:
        findings.append(Finding("pass", "github", "GitHub profile", resume.github))
        score += 6
        strengths.append("Public GitHub profile makes projects verifiable.")
    else:
        findings.append(
            Finding(
                "warn",
                "github",
                "No GitHub URL",
                "Engineering roles score higher with a GitHub or portfolio link.",
            )
        )

    if resume.linkedin:
        findings.append(Finding("pass", "linkedin", "LinkedIn profile", resume.linkedin))
        score += 3
    else:
        findings.append(
            Finding("warn", "linkedin", "No LinkedIn URL", "Add LinkedIn if you use it for recruiting.")
        )

    if 280 <= resume.word_count <= 950:
        findings.append(
            Finding("pass", "length", "Resume length", f"{resume.word_count} words — scannable.")
        )
        score += 6
    elif resume.word_count < 280:
        findings.append(
            Finding(
                "warn",
                "length",
                "Thin resume",
                f"Only {resume.word_count} words. Add impact bullets and a short summary.",
            )
        )
        improvements.append("Expand experience bullets with tools, scope, and outcomes.")
    else:
        findings.append(
            Finding(
                "warn",
                "length",
                "Long resume",
                f"{resume.word_count} words. Trim older or unrelated roles.",
            )
        )

    if resume.skills:
        findings.append(
            Finding(
                "pass",
                "skills",
                "Skills detected",
                ", ".join(resume.skills[:12]) + ("…" if len(resume.skills) > 12 else ""),
            )
        )
        score += min(10, len(resume.skills))
        strengths.append(f"{len(resume.skills)} technical skills parsed from the resume.")
    else:
        findings.append(
            Finding("fail", "skills", "No skills section", "Add a skills line ATS keyword matching can read.")
        )
        improvements.append("List tools and languages in a dedicated Skills section.")

    quantified = _quantified_bullets(resume)
    if quantified >= 3:
        findings.append(
            Finding("pass", "metrics", "Quantified impact", f"{quantified} bullets include numbers.")
        )
        score += 8
        strengths.append("Impact is quantified (percent, time, or scale).")
    elif quantified == 0:
        findings.append(
            Finding(
                "warn",
                "metrics",
                "No metrics",
                "Rewrite bullets with %, latency, users, revenue, or time saved.",
            )
        )
        improvements.append("Add 3+ bullets with measurable outcomes.")
    else:
        findings.append(
            Finding("warn", "metrics", "Few metrics", "Add more numeric outcomes so impact is obvious.")
        )
        score += 3

    verbs = _action_verb_count(resume)
    if verbs >= 3:
        score += 4
        findings.append(Finding("pass", "verbs", "Action verbs", "Bullets start with strong verbs."))
    else:
        findings.append(
            Finding(
                "warn",
                "verbs",
                "Weak bullets",
                "Start bullets with verbs like shipped, reduced, owned, or designed.",
            )
        )

    if resume.experience:
        score += min(8, 3 * len(resume.experience))
        findings.append(
            Finding("pass", "experience", "Work history", f"{len(resume.experience)} role(s) parsed.")
        )
    else:
        findings.append(
            Finding("fail", "experience", "No experience section", "Add roles with dates and bullets.")
        )
        improvements.append("Include an Experience section with dates.")

    if resume.projects:
        score += 4
        strengths.append("Projects are listed for portfolio evidence.")

    role_skills = extract_skills(target_role) if target_role else []
    matched, missing = skill_overlap(resume.skills, role_skills)
    if target_role and role_skills:
        if matched:
            score += min(10, 2 * len(matched))
            findings.append(
                Finding(
                    "pass",
                    "role-fit",
                    "Role keyword overlap",
                    "Matched: " + ", ".join(matched[:8]),
                )
            )
        if missing:
            findings.append(
                Finding(
                    "warn",
                    "role-gap",
                    "Role keyword gaps",
                    "Not found: " + ", ".join(missing[:8]),
                )
            )
            improvements.append(
                "If you have used "
                + ", ".join(missing[:5])
                + ", say so explicitly — ATS will not infer it."
            )

    llm_notes: dict[str, Any] = {}
    llm_used = False
    recruiter_score = None
    try:
        llm_notes = _optional_llm_review(resume, target_role)
        if llm_notes:
            llm_used = True
            recruiter_score = llm_notes.get("total_score")
            for item in llm_notes.get("key_strengths") or []:
                if item not in strengths:
                    strengths.append(item)
            for item in llm_notes.get("areas_for_improvement") or []:
                if item not in improvements:
                    improvements.append(item)
    except Exception as exc:  # LLM is optional; never fail the heuristic review
        llm_notes = {"error": str(exc)}

    overall = max(0, min(100, score))
    if not strengths:
        strengths.append("Resume parsed successfully and is ready for job matching.")
    if not improvements:
        improvements.append("Tailor the top 3 bullets to each posting before you apply.")

    return ApplicationReview(
        overall=overall,
        recruiter_score=recruiter_score,
        findings=findings,
        strengths=strengths[:6],
        improvements=improvements[:6],
        target_role=target_role,
        matched_keywords=matched,
        missing_keywords=missing,
        llm_used=llm_used,
        llm_notes=llm_notes,
    )


def _optional_llm_review(resume: ParsedResume, target_role: str) -> dict[str, Any]:
    """Use the existing evaluator if the original stack is installed and configured."""
    try:
        from evaluator import ResumeEvaluator
        from models import EvaluationData
        from prompt import DEFAULT_MODEL, MODEL_PARAMETERS
    except ImportError:
        return {}

    params = MODEL_PARAMETERS.get(DEFAULT_MODEL)
    evaluator = ResumeEvaluator(model_name=DEFAULT_MODEL, model_params=params)
    text = resume_plain_text(resume)
    if target_role:
        text += f"\n\n=== TARGET ROLE ===\n{target_role}"
    evaluation: EvaluationData = evaluator.evaluate_resume(text)
    scores = evaluation.scores
    total = (
        scores.open_source.score
        + scores.self_projects.score
        + scores.production.score
        + scores.technical_skills.score
        + evaluation.bonus_points.total
        - evaluation.deductions.total
    )
    return {
        "total_score": round(total, 1),
        "open_source": scores.open_source.score,
        "self_projects": scores.self_projects.score,
        "production": scores.production.score,
        "technical_skills": scores.technical_skills.score,
        "key_strengths": evaluation.key_strengths,
        "areas_for_improvement": evaluation.areas_for_improvement,
        "bonus": evaluation.bonus_points.breakdown,
        "deductions": evaluation.deductions.reasons,
        "raw": json.loads(evaluation.model_dump_json()),
    }
