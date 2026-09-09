"""Review, match, search, materials, and tracker tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from job_agent.match import rank_jobs, score_fit
from job_agent.materials import build_packet
from job_agent.parser import parse_resume_text
from job_agent.review import review_application
from job_agent.search import filter_jobs, load_catalog, search_jobs
from job_agent.tracker import Tracker

SAMPLE = Path("job_agent/data/sample_resume.md").read_text(encoding="utf-8")


class ReviewTests(unittest.TestCase):
    def test_sample_scores_well_for_backend(self) -> None:
        parsed = parse_resume_text(SAMPLE)
        review = review_application(parsed, target_role="Senior backend engineer python fastapi")
        self.assertGreaterEqual(review.overall, 70)
        self.assertTrue(any(item.code == "email" and item.severity == "pass" for item in review.findings))
        self.assertIn("python", review.matched_keywords)

    def test_thin_resume_warns(self) -> None:
        parsed = parse_resume_text("Sam Only\nsam@example.com\n")
        review = review_application(parsed, target_role="python")
        self.assertLess(review.overall, 70)
        codes = {item.code for item in review.findings}
        self.assertIn("skills", codes)

    def test_supply_chain_review_skips_github_warn(self) -> None:
        parsed = parse_resume_text(
            "Hiram Castillo\nsupply@example.com\n(904) 555-0100\nSt. Augustine, Florida\n\n"
            "SUMMARY\nProcurement and logistics operations.\n\n"
            "CORE SKILLS\nprocurement, logistics, excel\n\n"
            "RELEVANT EXPERIENCE\nPurchaser — Example (2020–2023)\n- Managed vendor invoices\n"
        )
        review = review_application(parsed, target_role="supply chain procurement")
        codes = {item.code: item.severity for item in review.findings}
        self.assertNotEqual(codes.get("github"), "warn")


class SearchMatchTests(unittest.TestCase):
    def test_catalog_loads(self) -> None:
        jobs = load_catalog()
        self.assertGreaterEqual(len(jobs), 15)
        ids = {job.id for job in jobs}
        self.assertIn("harborlight-ai-automation", ids)
        self.assertIn("watchpoint-soc-junior", ids)
        self.assertIn("tidewater-procurement", ids)

    def test_python_query_returns_backend_roles(self) -> None:
        result = search_jobs(query="python fastapi", include_live=False)
        ids = [job["id"] for job in result["jobs"]]
        self.assertIn("fieldnote-python", ids)
        self.assertIn("northstar-backend-python", ids)

    def test_remote_filter(self) -> None:
        jobs = load_catalog()
        remote = filter_jobs(jobs, remote_only=True)
        self.assertTrue(all(job.remote for job in remote))
        self.assertTrue(any(not job.remote for job in jobs))

    def test_remote_united_states_pref_keeps_remote_jobs(self) -> None:
        jobs = load_catalog()
        matched = filter_jobs(jobs, query="automation", remote_only=True, location="Remote / United States")
        ids = {job.id for job in matched}
        self.assertIn("harborlight-ai-automation", ids)
        self.assertIn("lumen-ai-ops", ids)

    def test_backend_resume_ranks_python_above_go(self) -> None:
        parsed = parse_resume_text(SAMPLE)
        jobs = {job.id: job for job in load_catalog()}
        ranked = rank_jobs(parsed, [jobs["fieldnote-python"], jobs["keel-go-backend"]])
        self.assertEqual(ranked[0][0].id, "fieldnote-python")
        self.assertGreater(ranked[0][1].score, ranked[1][1].score)

    def test_security_plus_ops_resume_beats_go_backend(self) -> None:
        text = """
ERIC HATCH
hatcheric950@example.com
(207) 468-6688
Remote / United States

SUMMARY
AI automation specialist with CompTIA Network+ and Security+, n8n, Zapier, Neon, and Supabase.

SKILLS
workflow automation, prompt engineering, n8n, Zapier, Neon, Supabase, Verbal, Salesforce, CRM, PII, help desk, Network+, Security+

EXPERIENCE
Founder — NEXUS AI Agency (2024–Present)
- Built Claude workflows in n8n and Zapier
"""
        parsed = parse_resume_text(text)
        jobs = {job.id: job for job in load_catalog()}
        ranked = rank_jobs(
            parsed,
            [jobs["lumen-ai-ops"], jobs["cedar-it-support-security"], jobs["keel-go-backend"]],
        )
        self.assertNotEqual(ranked[0][0].id, "keel-go-backend")
        cedar = next(fit for job, fit in ranked if job.id == "cedar-it-support-security")
        lumen = next(fit for job, fit in ranked if job.id == "lumen-ai-ops")
        keel = next(fit for job, fit in ranked if job.id == "keel-go-backend")
        self.assertGreater(cedar.score, keel.score)
        self.assertGreater(lumen.score, keel.score)
        self.assertIn("security+", cedar.matched_skills)
        self.assertIn("n8n", lumen.matched_skills)

    def test_supply_chain_resume_ranks_procurement_above_go(self) -> None:
        text = """
Hiram Castillo
supply@example.com
(904) 555-0100
St. Augustine, Florida 32080

PROFESSIONAL SUMMARY
Supply chain, procurement and operations professional with invoice auditing and customs compliance.

CORE SKILLS
Procurement, vendor management, logistics, customs, Excel, cost analysis, sourcing

RELEVANT EXPERIENCE
Purchaser — Example Construction — Panama 09/2020 – 04/2023
- Negotiated vendor rates and managed the procure-to-pay lifecycle
- Reconciled invoices against purchase orders
"""
        parsed = parse_resume_text(text)
        jobs = {job.id: job for job in load_catalog()}
        ranked = rank_jobs(
            parsed,
            [jobs["tidewater-procurement"], jobs["isthmus-import-compliance"], jobs["keel-go-backend"]],
        )
        self.assertNotEqual(ranked[0][0].id, "keel-go-backend")
        proc = next(fit for job, fit in ranked if job.id == "tidewater-procurement")
        customs = next(fit for job, fit in ranked if job.id == "isthmus-import-compliance")
        keel = next(fit for job, fit in ranked if job.id == "keel-go-backend")
        self.assertGreater(proc.score, keel.score)
        self.assertGreater(customs.score, keel.score)
        self.assertIn("procurement", proc.matched_skills)


class MaterialsAndTrackerTests(unittest.TestCase):
    def test_cover_letter_uses_facts(self) -> None:
        parsed = parse_resume_text(SAMPLE)
        job = next(job for job in load_catalog() if job.id == "fieldnote-python")
        fit = score_fit(parsed, job, target_role="backend")
        packet = build_packet(parsed, job, fit)
        self.assertIn("Alex Rivera", packet.cover_letter)
        self.assertIn("Fieldnote", packet.cover_letter)
        self.assertGreaterEqual(len(packet.tailored_bullets), 1)

    def test_apply_requires_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = Tracker(Path(tmp) / "t.db")
            tracker.upsert_job({"id": "job-1", "title": "Eng", "company": "X"})
            app = tracker.create_application("job-1", {"cover_letter": "hi"}, {"score": 80})
            with self.assertRaises(ValueError):
                tracker.mark_applied(app["id"], confirm=False)
            done = tracker.mark_applied(app["id"], confirm=True, notes="submitted")
            self.assertEqual(done["status"], "applied")
            self.assertIsNotNone(done["applied_at"])
            tracker.close()


if __name__ == "__main__":
    unittest.main()
