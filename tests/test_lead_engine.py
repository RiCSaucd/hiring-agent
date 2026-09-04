"""Nexus Lead Engine scoring, hunt, pipeline, and HTTP desk tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from lead_engine.hunt import extract_printed_contacts, filter_hunt
from lead_engine.locations import autocomplete, map_point
from lead_engine.pipeline import apply_gates, next_status
from lead_engine.scoring import (
    SAMPLE_CSV,
    is_safe_to_email,
    leads_to_csv,
    normalize_prospect,
    parse_prospect_csv,
    score_lead,
    validate_email,
)
from lead_engine.server import start_background
from lead_engine.service import NexusDesk


class ScoringTests(unittest.TestCase):
    def test_missing_and_disposable_are_not_safe(self) -> None:
        self.assertEqual(validate_email(""), "missing")
        self.assertEqual(validate_email("drop@mailinator.com"), "disposable")
        self.assertEqual(validate_email("info@coastalridge.com"), "role")
        self.assertEqual(validate_email("marcus.ellison@coastalridge.com"), "valid")
        self.assertFalse(is_safe_to_email("missing"))
        self.assertFalse(is_safe_to_email("disposable"))
        self.assertTrue(is_safe_to_email("valid"))

    def test_never_invents_email_on_normalize(self) -> None:
        row = normalize_prospect(
            {
                "full_name": "Chris Carasella",
                "title": "Director of Property Management",
                "company": "Suncoast Property Management",
                "email": "",
                "county": "Duval",
                "phone": "(904) 517-5939",
            }
        )
        self.assertEqual(row["email"], "")
        self.assertEqual(row["email_status"], "missing")
        self.assertFalse(row["is_safe_to_email"])

    def test_hot_threshold(self) -> None:
        scored = score_lead(
            title="Regional Property Manager",
            company="Coastal Ridge",
            county="Duval",
            phone="9045550142",
            email_status="valid",
            about_summary="Oversees a First Coast garden-style portfolio of garden units.",
            headline="RPM · Coastal Ridge",
        )
        self.assertGreaterEqual(scored["score"], 75)
        self.assertEqual(scored["temperature"], "Hot")
        self.assertLessEqual(scored["score"], 100)

    def test_csv_roundtrip(self) -> None:
        rows = parse_prospect_csv(SAMPLE_CSV)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["full_name"], "Rosa Delgado")
        csv_text = leads_to_csv([normalize_prospect(rows[0])])
        self.assertIn("rosa.delgado@tidewaterres.com", csv_text)
        self.assertIn("is_safe_to_email", csv_text)


class HuntAndPipelineTests(unittest.TestCase):
    def test_property_manager_hunt_returns_first_coast(self) -> None:
        hits = filter_hunt(title="Property Manager", location="Jacksonville")
        self.assertGreaterEqual(len(hits), 6)
        self.assertTrue(any(hit["id"] == "hunt_chris" for hit in hits))
        self.assertTrue(all(not hit["email"] for hit in hits))

    def test_extract_only_printed_emails(self) -> None:
        html = """
        <html><body>
          <a href="mailto:hello@suncoast.example">hello@suncoast.example</a>
          <p>Ignore this.png@cdn.example</p>
          <a href="https://linkedin.com/company/suncoast">li</a>
        </body></html>
        """
        contacts = extract_printed_contacts(html)
        self.assertEqual(contacts["emails"], ["hello@suncoast.example"])
        self.assertIn("linkedin", contacts["socials"])

    def test_autocomplete_jacksonville(self) -> None:
        hits = autocomplete("jack")
        self.assertTrue(any(city["name"] == "Jacksonville" for city in hits))
        self.assertIsNotNone(map_point(30.3322, -81.6557))
        self.assertIsNone(map_point(34.05, -118.24))

    def test_pipeline_drops_disposable(self) -> None:
        lead = apply_gates(
            {"id": "x", "status": "new"},
            {"full_name": "Temp", "email": "drop@mailinator.com", "company": "Pop-up"},
        )
        self.assertEqual(lead["status"], "invalid")
        self.assertEqual(next_status(lead), "invalid")


class DeskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.desk = NexusDesk(Path(self.tmp.name) / "nexus.db", seed=True)

    def tearDown(self) -> None:
        self.desk.close()
        self.tmp.cleanup()

    def test_hunt_import_pipeline_csv(self) -> None:
        hunt = self.desk.hunt(title="Property Manager", location="Jacksonville")
        self.assertGreater(hunt["count"], 3)
        imported = self.desk.import_hits([hit["id"] for hit in hunt["hits"][:3]])
        self.assertGreaterEqual(imported["created"] + imported["updated"], 1)
        result = self.desk.run_pipeline()
        self.assertIn("updated", result)
        csv_text = self.desk.export_csv()
        self.assertIn("full_name", csv_text)
        safe = self.desk.export_csv(safe_only=True)
        self.assertIn("is_safe_to_email", safe)
        self.assertNotIn("mailinator", safe)

    def test_seed_has_invalid_junk_row(self) -> None:
        leads = {lead["full_name"]: lead for lead in self.desk.list_leads()}
        self.assertEqual(leads["Temp Drop"]["email_status"], "disposable")
        self.assertFalse(leads["Temp Drop"]["is_safe_to_email"])
        self.assertGreaterEqual(leads["Marcus Ellison"]["lead_score"], 75)


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.server = start_background(
            host="127.0.0.1",
            port=0,
            db_path=Path(self.tmp.name) / "desk.db",
        )
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.desk.close()
        self.server.server_close()
        self.tmp.cleanup()

    def _json(self, path: str, payload: dict | None = None) -> dict:
        data = None
        headers = {}
        method = "GET"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_hunt_pipeline_page(self) -> None:
        health = self._json("/health")
        self.assertTrue(health["ok"])
        hunt = self._json("/api/hunt", {"title": "Property Manager", "location": "Jacksonville"})
        self.assertGreaterEqual(hunt["count"], 6)
        imported = self._json("/api/hunt/import", {"ids": [hunt["hits"][0]["id"]]})
        self.assertIn("created", imported)
        pipeline = self._json("/api/pipeline", {})
        self.assertIn("hot_ids", pipeline)
        page = urlopen(f"http://127.0.0.1:{self.port}/", timeout=10).read().decode("utf-8")
        self.assertIn("Lead Engine", page)
        self.assertIn("Emails are never invented", page)
        css = urlopen(f"http://127.0.0.1:{self.port}/styles.css", timeout=10).read().decode("utf-8")
        self.assertIn("--hot", css)


if __name__ == "__main__":
    unittest.main()
