"""Tests for heuristic resume parsing and skill extraction."""

from __future__ import annotations

import unittest
from pathlib import Path

from job_agent.parser import parse_resume_text
from job_agent.pdfutil import extract_text_from_simple_pdf, load_resume_text, write_simple_pdf
from job_agent.skills import extract_skills

SAMPLE = Path("job_agent/data/sample_resume.md").read_text(encoding="utf-8")


class SkillTests(unittest.TestCase):
    def test_does_not_treat_javascript_as_java(self) -> None:
        self.assertEqual(extract_skills("javascript react"), ["javascript", "react"])
        self.assertNotIn("java", extract_skills("javascript"))

    def test_does_not_treat_good_as_go(self) -> None:
        self.assertNotIn("go", extract_skills("good documentation"))
        self.assertIn("go", extract_skills("Wrote gRPC services in Go and Kubernetes"))


class ParserTests(unittest.TestCase):
    def test_sample_resume(self) -> None:
        parsed = parse_resume_text(SAMPLE, filename="sample_resume.md")
        self.assertEqual(parsed.name, "Alex Rivera")
        self.assertEqual(parsed.email, "alex.rivera@example.com")
        self.assertTrue(parsed.github.startswith("https://github.com/"))
        self.assertIn("python", parsed.skills)
        self.assertIn("fastapi", parsed.skills)
        self.assertGreaterEqual(len(parsed.experience), 2)
        self.assertGreaterEqual(len(parsed.experience[0].highlights), 2)
        self.assertGreater(parsed.word_count, 200)

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            parse_resume_text("   ")

    def test_professional_headings(self) -> None:
        text = """
ERIC HATCH
hatcheric950@example.com
Remote

PROFESSIONAL SUMMARY
CompTIA-certified automation specialist using Claude and Salesforce.

CERTIFICATIONS & LICENSES
CompTIA Certified
AI Automation Certified

PROFESSIONAL EXPERIENCE
Founder — NEXUS AI Agency (2024–Present)
- Built Claude workflows and documented SOPs
- Rebuilt a follow-up system and cut 3 hours to 30 minutes

TECHNICAL & PROFESSIONAL SKILLS
Claude, ChatGPT, prompt engineering, Salesforce, workflow automation, compliance, PII, help desk

EDUCATION
Bachelor's Degree — Nichols College
"""
        parsed = parse_resume_text(text)
        self.assertEqual(parsed.name, "ERIC HATCH")
        self.assertTrue(parsed.summary)
        self.assertGreaterEqual(len(parsed.experience), 1)
        self.assertIn("salesforce", parsed.skills)
        self.assertIn("workflow automation", parsed.skills)
        self.assertIn("prompt engineering", parsed.skills)


class PdfTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        path = Path("var/test_resume.pdf")
        write_simple_pdf(path, ["Alex Rivera", "alex.rivera@example.com", "SKILLS", "Python FastAPI"])
        text = load_resume_text(path)
        self.assertIn("Alex Rivera", text)
        self.assertIn("Python FastAPI", text)
        raw = extract_text_from_simple_pdf(path.read_bytes())
        self.assertIn("alex.rivera@example.com", raw)


if __name__ == "__main__":
    unittest.main()
