"""Stdlib HTTP desk for the Nexus Lead Engine."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from lead_engine.scoring import SAMPLE_CSV
from lead_engine.service import DEFAULT_DB, NexusDesk

WEB_DIR = Path(__file__).resolve().parent / "web"


def json_bytes(payload: Any, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def error_payload(message: str, status: int = 400) -> tuple[int, bytes, str]:
    return json_bytes({"error": message}, status=status)


class NexusHandler(BaseHTTPRequestHandler):
    desk: NexusDesk

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _send(self, status: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Cache-Control", "no-store")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        try:
            if path in {"/", "/index.html"}:
                self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
                return
            if path == "/styles.css":
                self._send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
                return
            if path == "/app.js":
                self._send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
                return
            if path == "/health":
                self._send(*json_bytes({"ok": True, "engine": "nexus-lead-engine"}))
                return
            if path == "/api/status":
                self._send(*json_bytes(self.desk.status()))
                return
            if path == "/api/snapshot":
                self._send(*json_bytes(self.desk.snapshot()))
                return
            if path == "/api/leads":
                self._send(
                    *json_bytes(
                        {
                            "leads": self.desk.list_leads(
                                temperature=query.get("temperature"),
                                county=query.get("county"),
                            )
                        }
                    )
                )
                return
            if path == "/api/hunt":
                self._send(
                    *json_bytes(
                        self.desk.hunt(
                            query=query.get("q") or query.get("query") or "",
                            title=query.get("title") or "Property Manager",
                            location=query.get("location") or "Jacksonville",
                        )
                    )
                )
                return
            if path == "/api/autocomplete":
                self._send(*json_bytes({"predictions": self.desk.suggest_locations(query.get("input") or "")}))
                return
            if path == "/api/geocode":
                hit = self.desk.geocode_location(query.get("q") or query.get("input") or "")
                if not hit:
                    self._send(*error_payload("Location not found", 404))
                    return
                self._send(*json_bytes(hit))
                return
            if path == "/api/captures":
                self._send(*json_bytes({"captures": self.desk.list_captures()}))
                return
            if path == "/api/batches":
                self._send(*json_bytes({"batches": self.desk.list_batches()}))
                return
            if path == "/api/activity":
                self._send(*json_bytes({"activity": self.desk.activity()}))
                return
            if path == "/api/export.csv":
                csv_text = self.desk.export_csv(safe_only=query.get("safe") in {"1", "true"})
                self._send(
                    200,
                    csv_text.encode("utf-8"),
                    "text/csv; charset=utf-8",
                    extra={"Content-Disposition": "attachment; filename=nexus-leads.csv"},
                )
                return
            if path == "/api/sample.csv":
                self._send(*json_bytes({"csv": SAMPLE_CSV}))
                return
            self._send(*error_payload("Not found", 404))
        except ValueError as exc:
            self._send(*error_payload(str(exc), 400))
        except KeyError as exc:
            self._send(*error_payload(str(exc), 404))
        except Exception as exc:
            self._send(*error_payload(str(exc), 500))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json()
            if path == "/api/hunt":
                self._send(
                    *json_bytes(
                        self.desk.hunt(
                            query=str(body.get("query") or body.get("q") or ""),
                            title=str(body.get("title") or "Property Manager"),
                            location=str(body.get("location") or "Jacksonville"),
                        )
                    )
                )
                return
            if path == "/api/hunt/import":
                ids = body.get("ids") or body.get("hit_ids") or []
                if not isinstance(ids, list):
                    raise ValueError("ids must be a list")
                self._send(*json_bytes(self.desk.import_hits([str(item) for item in ids])))
                return
            if path == "/api/prospects":
                rows = body.get("prospects") or body.get("rows") or []
                if not isinstance(rows, list):
                    raise ValueError("prospects must be a list")
                self._send(*json_bytes(self.desk.add_prospects(rows)))
                return
            if path == "/api/import-csv":
                text = str(body.get("csv") or body.get("text") or "")
                self._send(*json_bytes(self.desk.import_csv(text)))
                return
            if path == "/api/pipeline":
                ids = body.get("ids")
                if ids is not None and not isinstance(ids, list):
                    raise ValueError("ids must be a list")
                self._send(
                    *json_bytes(
                        self.desk.run_pipeline([str(item) for item in ids] if ids else None)
                    )
                )
                return
            if path == "/api/enrich":
                url = str(body.get("url") or "")
                self._send(*json_bytes(self.desk.enrich_url(url)))
                return
            if path.startswith("/api/leads/") and path.endswith("/update"):
                lead_id = path[len("/api/leads/") : -len("/update")]
                self._send(*json_bytes(self.desk.update_lead(lead_id, body)))
                return
            if path == "/api/deliver":
                ids = body.get("ids") or []
                if not isinstance(ids, list):
                    raise ValueError("ids must be a list")
                self._send(
                    *json_bytes(
                        self.desk.deliver(
                            [str(item) for item in ids],
                            client_name=str(body.get("client_name") or body.get("clientName") or ""),
                            notes=str(body.get("notes") or ""),
                        )
                    )
                )
                return
            if path == "/api/captures":
                self._send(*json_bytes(self.desk.add_capture(body)))
                return
            if path == "/api/reset":
                self._send(*json_bytes(self.desk.reset_demo()))
                return
            self._send(*error_payload("Not found", 404))
        except ValueError as exc:
            self._send(*error_payload(str(exc), 400))
        except KeyError as exc:
            self._send(*error_payload(str(exc), 404))
        except Exception as exc:
            self._send(*error_payload(str(exc), 500))

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/leads/"):
                lead_id = path[len("/api/leads/") :]
                if not lead_id:
                    raise ValueError("lead id required")
                self.desk.delete_lead(lead_id)
                self._send(*json_bytes({"ok": True, "id": lead_id}))
                return
            self._send(*error_payload("Not found", 404))
        except KeyError as exc:
            self._send(*error_payload(str(exc), 404))
        except Exception as exc:
            self._send(*error_payload(str(exc), 500))

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._send(*error_payload("Not found", 404))
            return
        self._send(200, path.read_bytes(), content_type)


def make_server(
    host: str = "0.0.0.0",
    port: int = 8770,
    db_path: str | Path = DEFAULT_DB,
) -> ThreadingHTTPServer:
    desk = NexusDesk(db_path=db_path)

    class BoundHandler(NexusHandler):
        pass

    BoundHandler.desk = desk
    server = ThreadingHTTPServer((host, port), BoundHandler)
    server.desk = desk  # type: ignore[attr-defined]
    return server


def serve_forever(host: str = "0.0.0.0", port: int = 8770, db_path: str | Path = DEFAULT_DB) -> None:
    server = make_server(host=host, port=port, db_path=db_path)
    print(f"Nexus Lead Engine on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.desk.close()  # type: ignore[attr-defined]
        server.server_close()


def start_background(host: str = "127.0.0.1", port: int = 0, db_path: str | Path = DEFAULT_DB) -> ThreadingHTTPServer:
    server = make_server(host=host, port=port, db_path=db_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
