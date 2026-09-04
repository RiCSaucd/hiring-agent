"""Application packet: cover letter, tailored bullets, screening answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from job_agent.match import JobFit
from job_agent.parser import ParsedResume
from job_agent.search import Job


@dataclass
class ApplicationPacket:
    cover_letter: str
    tailored_bullets: list[str]
    screening_answers: dict[str, str]
    paste_checklist: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cover_letter": self.cover_letter,
            "tailored_bullets": self.tailored_bullets,
            "screening_answers": self.screening_answers,
            "paste_checklist": self.paste_checklist,
        }


def _best_highlights(resume: ParsedResume, keywords: list[str], limit: int = 4) -> list[str]:
    needles = [key.lower() for key in keywords]
    scored: list[tuple[int, str]] = []
    for job in resume.experience:
        for highlight in job.highlights:
            hay = highlight.lower()
            hits = sum(1 for needle in needles if needle and needle in hay)
            if any(ch.isdigit() for ch in highlight):
                hits += 1
            scored.append((hits, highlight))
    scored.sort(key=lambda item: item[0], reverse=True)
    unique: list[str] = []
    for _, text in scored:
        if text not in unique:
            unique.append(text)
        if len(unique) >= limit:
            break
    if len(unique) < 2:
        for job in resume.experience:
            unique.extend(job.highlights[:2])
    return unique[:limit]


def _optional_llm_cover_letter(resume: ParsedResume, job: Job) -> str:
    try:
        from llm_utils import initialize_llm_provider
        from prompt import DEFAULT_MODEL, MODEL_PARAMETERS
    except ImportError:
        return ""
    try:
        provider = initialize_llm_provider(DEFAULT_MODEL)
        params = MODEL_PARAMETERS.get(DEFAULT_MODEL, {"temperature": 0.3, "top_p": 0.9})
        prompt = (
            "Write a 180-220 word cover letter. No demographic assumptions. "
            "Use only facts from the resume. Do not invent employers or metrics.\n\n"
            f"CANDIDATE:\n{resume.name}\n{resume.summary}\n"
            f"SKILLS: {', '.join(resume.skills)}\n"
            f"ROLE: {job.title} at {job.company}\n"
            f"JOB:\n{job.description[:1800]}\n"
        )
        response = provider.chat(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You write concise, specific job application letters."},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": params.get("temperature", 0.3), "top_p": params.get("top_p", 0.9)},
        )
        return str(response.get("message", {}).get("content") or "").strip()
    except Exception:
        return ""


def build_packet(resume: ParsedResume, job: Job, fit: JobFit) -> ApplicationPacket:
    highlights = _best_highlights(resume, fit.matched_skills + job.tags)
    letter = _optional_llm_cover_letter(resume, job)
    if not letter:
        highlight_lines = "\n".join(f"- {item}" for item in highlights[:3]) or "- Built and shipped production software."
        gap_line = ""
        if fit.missing_skills:
            gap_line = (
                f" Where the posting emphasizes {', '.join(fit.missing_skills[:3])}, "
                "I would want to learn how your team uses those in production."
            )
        letter = (
            f"Dear {job.company} hiring team,\n\n"
            f"I am applying for the {job.title} role. I am a {resume.experience[0].title if resume.experience else 'software'} "
            f"candidate with experience across {', '.join(resume.skills[:6]) or 'software delivery'}. "
            f"{resume.summary or ''}\n\n"
            f"A few facts from my work that map to this posting:\n{highlight_lines}\n\n"
            f"I am especially interested in {job.company} because the role focuses on "
            f"{', '.join(job.tags[:4]) or job.title.lower()}.{gap_line}\n\n"
            f"I would welcome a conversation about how I can help. Materials and links are in my resume"
            f"{' and ' + resume.github if resume.github else ''}.\n\n"
            f"Thank you,\n{resume.name or 'Applicant'}"
        )

    answers = {
        "why_this_role": (
            f"The {job.title} role matches work I have already done with "
            f"{', '.join(fit.matched_skills[:5]) or 'the stack in my resume'}. "
            f"I want to apply that in {job.company}'s environment."
        ),
        "why_this_company": (
            f"I am applying to {job.company} specifically for this posting, not spraying a generic letter. "
            f"The description's focus on {', '.join(job.tags[:3]) or job.title} is the fit."
        ),
        "work_authorization": "I can confirm work authorization details on the employer's application form.",
        "availability": "I can start after a standard notice period and am available for interviews on weekdays.",
    }

    tailored = []
    for item in highlights:
        extra = ""
        if fit.matched_skills:
            extra = f" (maps to {fit.matched_skills[0]})"
        tailored.append(item + extra)

    checklist = [
        "Open the employer apply URL — this agent does not submit forms for you.",
        "Paste the cover letter into the cover-letter or additional-info field.",
        "Upload the same resume file you reviewed here.",
        "Fill required legal / work-authorization questions yourself.",
        "Mark the job Applied in the tracker after you submit on their site.",
    ]
    if resume.github:
        checklist.insert(2, f"Confirm GitHub ({resume.github}) is public.")

    return ApplicationPacket(
        cover_letter=letter.strip(),
        tailored_bullets=tailored,
        screening_answers=answers,
        paste_checklist=checklist,
    )
