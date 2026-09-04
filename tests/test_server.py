"""HTTP desk tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from job_agent.server import start_background


SAMPLE = Path("job_agent/data/sample_resume.md").read_text(encoding="utf-8")


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

    def _json(self, path: str, payload: dict | None = None, method: str | None = None) -> dict:
        data = None
        headers = {}
        verb = method
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            verb = verb or "POST"
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers=headers,
            method=verb or "GET",
        )
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_and_flow(self) -> None:
        health = self._json("/health")
        self.assertTrue(health["ok"])
        ingested = self._json(
            "/api/resume",
            {
                "filename": "sample_resume.md",
                "text": SAMPLE,
                "target_role": "backend engineer",
                "remote_only": True,
            },
        )
        self.assertEqual(ingested["resume"]["name"], "Alex Rivera")
        self.assertGreaterEqual(ingested["review"]["overall"], 70)
        jobs = self._json("/api/jobs/search", {"query": "python", "include_live": False, "remote_only": True})
        self.assertGreater(jobs["count"], 3)
        job_id = jobs["jobs"][0]["id"]
        application = self._json("/api/applications", {"job_id": job_id})
        self.assertEqual(application["status"], "draft")
        self.assertIn("cover_letter", application["packet"])
        with self.assertRaises(Exception):
            self._json(f"/api/applications/{application['id']}/apply", {"confirm": False})
        applied = self._json(
            f"/api/applications/{application['id']}/apply",
            {"confirm": True, "notes": "pasted into greenhouse"},
        )
        self.assertEqual(applied["status"], "applied")
        page = urlopen(f"http://127.0.0.1:{self.port}/", timeout=10).read().decode("utf-8")
        self.assertIn("Application Desk", page)


if __name__ == "__main__":
    unittest.main()
