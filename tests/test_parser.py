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

    def test_comptia_plus_certs_and_ops_tools(self) -> None:
        skills = extract_skills(
            "CompTIA Network+ and Security plus. I use n8n, Neon, Zapier, super base, Verbal."
        )
        for expected in (
            "network+",
            "security+",
            "comptia",
            "security",
            "n8n",
            "neon",
            "zapier",
            "supabase",
            "verbal",
        ):
            self.assertIn(expected, skills)
        self.assertNotIn("java", skills)

    def test_customer_service_aliases(self) -> None:
        skills = extract_skills(
            "Customer support and customer experience in Salesforce CRM. "
            "Life & Health and Property & Casualty licenses. Client success follow-up."
        )
        for expected in (
            "customer service",
            "customer success",
            "salesforce",
            "crm",
            "insurance",
        ):
            self.assertIn(expected, skills)

    def test_medical_sales_competency_aliases(self) -> None:
        skills = extract_skills(
            "Consultative and solution selling. Outside/field sales territory management. "
            "Eager to pivot into medical sales and prescription drug supplies. Contract negotiation. "
            "Salesforce CRM and pipeline forecasting."
        )
        for expected in (
            "consultative selling",
            "outside sales",
            "territory management",
            "medical sales",
            "contract negotiation",
            "pipeline",
            "client communication",
        ):
            self.assertIn(expected, skills)

    def test_security_plus_does_not_require_siem(self) -> None:
        skills = extract_skills("CompTIA Security+")
        self.assertIn("security+", skills)
        self.assertNotIn("siem", skills)
        self.assertNotIn("soc", skills)


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

    def test_formats_ten_digit_phone(self) -> None:
        parsed = parse_resume_text(
            "ERIC HATCH\nhatcheric950@example.com\n2074686688\nRemote\n\nSKILLS\nPython\n"
        )
        self.assertEqual(parsed.phone, "(207) 468-6688")

    def test_pipe_header_location_and_augustine_dates(self) -> None:
        text = """
ERIC HATCH
hatcheric950@example.com | (207) 468-6688 | Remote / United States | Open to full-time

EXPERIENCE
Vehicle Experience Specialist — Volkswagen of St. Augustine (Jan 2023–Present)
St. Augustine, FL
- Managed the customer lifecycle in CRM
"""
        parsed = parse_resume_text(text)
        self.assertEqual(parsed.location, "Remote / United States")
        self.assertEqual(parsed.experience[0].organization, "Volkswagen of St. Augustine")
        self.assertRegex(parsed.experience[0].dates, r"Jan 2023")
        self.assertNotIn("Augustine (Jan", parsed.experience[0].dates)

    def test_pipe_job_lines_and_core_competencies(self) -> None:
        text = """
ERIC HATCH
Saint Augustine, FL 32080 • hatcheric950@example.com • (207) 468-6688

PROFESSIONAL SUMMARY
Top-performing sales professional pivoting into medical sales.

PROFESSIONAL EXPERIENCE
Vehicle Experience Specialist | Volkswagen of St. Augustine | Saint Augustine, FL | 2023 – Present
- Closed an average of 12-15 vehicles per month

EDUCATION
Bachelor of Science in Business Marketing | Nichols College | Expected May 2025

CORE COMPETENCIES
Consultative & Solution Selling • Salesforce CRM • Contract Negotiation

REFERENCES
Wade Wahy
"""
        parsed = parse_resume_text(text)
        self.assertEqual(parsed.location, "Saint Augustine, FL 32080")
        self.assertEqual(parsed.experience[0].title, "Vehicle Experience Specialist")
        self.assertEqual(parsed.experience[0].organization, "Volkswagen of St. Augustine")
        self.assertIn("salesforce", parsed.skills)
        self.assertIn("consultative selling", parsed.skills)
        self.assertEqual(len(parsed.experience), 1)

    def test_wrapped_pipe_dates_yield_two_jobs(self) -> None:
        text = """
ERIC HATCH
Saint Augustine, FL 32080 • hatcheric950@gmail.com • (207) 468-6688

PROFESSIONAL EXPERIENCE
Vehicle Experience Specialist (Top 1% Regional Performer) | Volkswagen of St. Augustine | Saint Augustine, FL |
2023 – Present
- Ranked #1 salesperson (5x) and closed 12-15 vehicles per month

Outside Sales Associate | Shultz and Lyman | Augusta, ME | 2021 – 2022
- Achieved a 98% on-time order fulfillment rate

REFERENCES
Wade Wahy
"""
        parsed = parse_resume_text(text)
        self.assertEqual(len(parsed.experience), 2)
        self.assertEqual(parsed.experience[0].organization, "Volkswagen of St. Augustine")
        self.assertRegex(parsed.experience[0].dates, r"2023")
        self.assertIn("Present", parsed.experience[0].dates)
        self.assertEqual(parsed.experience[1].organization, "Shultz and Lyman")
        self.assertRegex(parsed.experience[1].dates, r"2021")
        self.assertNotIn("Wade", parsed.experience[0].title)
        self.assertNotIn("Wade", parsed.experience[1].title)

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
