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

    def test_supply_chain_tools(self) -> None:
        skills = extract_skills(
            "Procure-to-pay, vendor negotiation, customs compliance, invoice audit, Excel, demand planner."
        )
        for expected in (
            "procurement",
            "vendor management",
            "customs",
            "invoice auditing",
            "excel",
            "demand planning",
        ):
            self.assertIn(expected, skills)
        self.assertIn(
            "customs",
            extract_skills("Classified goods on the Harmonized Tariff Schedule and HTS line items."),
        )

    def test_cpsm_in_progress_is_not_held(self) -> None:
        self.assertNotIn(
            "cpsm",
            extract_skills("Certified Professional in Supply Management (CPSM) — in progress"),
        )
        self.assertIn("cpsm", extract_skills("CPSM, 2024"))


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
Saint Augustine, FL 32080 • hatcheric950@example.com • (207) 468-6688

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

    def test_core_skills_and_relevant_experience(self) -> None:
        text = """
Hiram Castillo
supply@example.com | (904) 555-0100 | St. Augustine, Florida 32080 | Bilingual: Spanish/English

PROFESSIONAL SUMMARY
Supply chain professional managing procure-to-pay.

CORE SKILLS
Procurement, vendor negotiation, customs compliance, Microsoft Excel

RELEVANT EXPERIENCE
Purchaser — Example Builders — Panama 09/2020 – 04/2023
- Managed the full procurement-to-payment lifecycle
- Negotiated carrier rates

Logistics Specialist — Example Builders — Panama
06/2018 – 09/2020
- Coordinated shipments and audited invoices
"""
        parsed = parse_resume_text(text)
        self.assertEqual(parsed.name, "Hiram Castillo")
        self.assertEqual(parsed.phone, "(904) 555-0100")
        self.assertIn("Florida", parsed.location)
        self.assertGreaterEqual(len(parsed.experience), 2)
        self.assertEqual(parsed.experience[0].title, "Purchaser")
        self.assertIn("Example Builders", parsed.experience[0].organization)
        self.assertRegex(parsed.experience[0].dates, r"09/2020")
        self.assertEqual(parsed.experience[1].title, "Logistics Specialist")
        self.assertIn("2018", parsed.experience[1].dates)
        self.assertIn("procurement", parsed.skills)
        self.assertTrue(parsed.summary)

    def test_references_are_not_jobs(self) -> None:
        text = """
HIRAMIS CASTILLO BARRAZA
hcastb@example.com | (904) 555-0100
St. Augustine, Florida 32080

RELEVANT EXPERIENCE
Purchaser — Example Builders — Panama 09/2020 – 04/2023
- Managed the full procurement-to-payment lifecycle

Logistics Specialist — Example Builders — Panama 06/2018 – 09/2020
- Coordinated shipments and audited invoices

REFERENCES
Carolina Sanchez — professional reference; contact details available upon request
Michelle Guleth — professional reference; contact details available upon request
"""
        parsed = parse_resume_text(text)
        self.assertEqual(parsed.email, "hcastb@example.com")
        self.assertEqual(len(parsed.experience), 2)
        blob = " ".join(
            f"{item.title} {item.organization} {item.raw}" for item in parsed.experience
        )
        self.assertNotIn("Sanchez", blob)
        self.assertNotIn("Guleth", blob)
        self.assertNotIn("Carolina", blob)

    def test_stacked_title_company_dates_and_continued_heading(self) -> None:
        text = """
HIRAMIS CASTILLO BARRAZA | 1
HIRAMIS CASTILLO BARRAZA
hcastb@icloud.com | 904-580-1586 | St. Augustine, FL

PROFESSIONAL SUMMARY
Bilingual logistics and procurement professional.

CORE SKILLS
Procure-to-pay, vendor negotiation, customs compliance, Microsoft Excel

PROFESSIONAL EXPERIENCE
Property Manager | Promoted from Sales
Isla Antigua | St. Augustine, FL | 2023 - Present
- Coordinate vendor relationships and purchasing needs
- Combined customer-facing sales experience with vendor communication

Purchaser
Bouygues Bâtiment International | Panama | Sep 2020 - Apr 2023
- Selected vendors and carriers and negotiated rates

HIRAMIS CASTILLO BARRAZA | 2
PROFESSIONAL EXPERIENCE CONTINUED
Imports Coordinator
Office Depot Panama | Panama | Oct 2017 - Jun 2018
- Reduced import costs by up to 50% through supplier negotiations
"""
        parsed = parse_resume_text(text)
        self.assertEqual(parsed.name, "HIRAMIS CASTILLO BARRAZA")
        self.assertEqual(parsed.email, "hcastb@icloud.com")
        self.assertEqual(parsed.phone, "(904) 580-1586")
        self.assertIn("Augustine", parsed.location)
        titles = [item.title for item in parsed.experience]
        orgs = [item.organization for item in parsed.experience]
        self.assertEqual(titles[0], "Property Manager")
        self.assertEqual(orgs[0], "Isla Antigua")
        self.assertRegex(parsed.experience[0].dates, r"2023")
        self.assertEqual(titles[1], "Purchaser")
        self.assertIn("Bouygues", orgs[1])
        self.assertRegex(parsed.experience[1].dates, r"2020")
        self.assertIn("Imports Coordinator", titles)
        blob = " ".join(titles)
        self.assertNotIn("CONTINUED", blob.upper())
        self.assertNotIn("HIRAMIS CASTILLO BARRAZA | 2", blob)


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
