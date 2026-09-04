"""Stdlib HTTP desk for the job-seeker agent."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from job_agent.service import DEFAULT_DB, HiringDesk

WEB_DIR = Path(__file__).resolve().parent / "web"


def json_bytes(payload: Any, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def error_payload(message: str, status: int = 400) -> tuple[int, bytes, str]:
    return json_bytes({"error": message}, status=status)


class DeskHandler(BaseHTTPRequestHandler):
    desk: HiringDesk

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

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Cache-Control", "no-store")
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
                self._send(*json_bytes({"ok": True}))
                return
            if path == "/api/profile":
                self._send(*json_bytes(self.desk.tracker.get_profile()))
                return
            if path == "/api/review":
                self._send(*json_bytes(self.desk.review(target_role=query.get("target_role"))))
                return
            if path == "/api/jobs":
                self._send(
                    *json_bytes(
                        self.desk.search(
                            query=query.get("q") or query.get("query") or "",
                            include_live=query.get("live", "1") not in {"0", "false"},
                            remote_only=_optional_bool(query.get("remote")),
                            location=query.get("location"),
                        )
                    )
                )
                return
            if path.startswith("/api/jobs/") and path.endswith("/fit"):
                job_id = path[len("/api/jobs/") : -len("/fit")]
                self._send(*json_bytes(self.desk.fit(job_id)))
                return
            if path == "/api/applications":
                self._send(*json_bytes({"applications": self.desk.applications()}))
                return
            if path == "/api/status":
                self._send(*json_bytes(self.desk.status()))
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
            if path in {"/api/resume", "/api/profile/resume"}:
                filename = str(body.get("filename") or "resume.md")
                if body.get("text"):
                    result = self.desk.ingest_resume_text(
                        filename=filename,
                        text=str(body["text"]),
                        target_role=str(body.get("target_role") or ""),
                        target_location=str(body.get("target_location") or ""),
                        remote_only=_optional_bool(body.get("remote_only")),
                    )
                elif body.get("content_b64"):
                    result = self.desk.ingest_resume_base64(
                        filename=filename,
                        content_b64=str(body["content_b64"]),
                        target_role=str(body.get("target_role") or ""),
                        target_location=str(body.get("target_location") or ""),
                        remote_only=_optional_bool(body.get("remote_only")),
                    )
                else:
                    raise ValueError("Provide text or content_b64")
                self._send(*json_bytes(result))
                return
            if path == "/api/preferences":
                self._send(
                    *json_bytes(
                        self.desk.set_preferences(
                            target_role=body.get("target_role"),
                            target_location=body.get("target_location"),
                            remote_only=_optional_bool(body.get("remote_only")),
                        )
                    )
                )
                return
            if path == "/api/jobs/search":
                self._send(
                    *json_bytes(
                        self.desk.search(
                            query=str(body.get("query") or ""),
                            include_live=bool(body.get("include_live", True)),
                            remote_only=_optional_bool(body.get("remote_only")),
                            location=body.get("location"),
                        )
                    )
                )
                return
            if path == "/api/jobs/paste":
                self._send(*json_bytes(self.desk.paste_job(body)))
                return
            if path == "/api/applications":
                job_id = str(body.get("job_id") or "")
                if not job_id:
                    raise ValueError("job_id is required")
                self._send(*json_bytes(self.desk.prepare(job_id)))
                return
            if path.startswith("/api/applications/") and path.endswith("/apply"):
                raw_id = path[len("/api/applications/") : -len("/apply")]
                application_id = int(raw_id)
                if not body.get("confirm"):
                    raise ValueError("Refusing to mark applied without confirm=true")
                notes = str(body.get("notes") or "")
                self._send(*json_bytes(self.desk.apply(application_id, confirm=True, notes=notes)))
                return
            self._send(*error_payload("Not found", 404))
        except ValueError as exc:
            self._send(*error_payload(str(exc), 400))
        except KeyError as exc:
            self._send(*error_payload(str(exc), 404))
        except Exception as exc:
            self._send(*error_payload(str(exc), 500))

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._send(*error_payload("Not found", 404))
            return
        self._send(200, path.read_bytes(), content_type)


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None


def make_server(
    host: str = "0.0.0.0",
    port: int = 8765,
    db_path: str | Path = DEFAULT_DB,
) -> ThreadingHTTPServer:
    desk = HiringDesk(db_path=db_path)

    class BoundHandler(DeskHandler):
        pass

    BoundHandler.desk = desk
    server = ThreadingHTTPServer((host, port), BoundHandler)
    server.desk = desk  # type: ignore[attr-defined]
    return server


def serve_forever(host: str = "0.0.0.0", port: int = 8765, db_path: str | Path = DEFAULT_DB) -> None:
    server = make_server(host=host, port=port, db_path=db_path)
    print(f"Hiring desk on http://{host}:{port}")
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
