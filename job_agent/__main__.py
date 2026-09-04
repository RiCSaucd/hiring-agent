"""CLI: review a resume, search jobs, prepare packets, and serve the desk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from job_agent.service import DEFAULT_DB, HiringDesk


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path for the local tracker")

    parser = argparse.ArgumentParser(
        prog="python -m job_agent",
        description="Review your application and apply to matching jobs (human confirm before apply).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", parents=[shared], help="Parse and review a resume")
    review.add_argument("resume", help="Path to resume (.md, .txt, or simple .pdf)")
    review.add_argument("--role", default="", help="Target role, e.g. 'backend engineer'")
    review.add_argument("--location", default="", help="Preferred location")
    review.add_argument("--onsite", action="store_true", help="Do not prefer remote-only jobs")

    search = sub.add_parser(
        "search", parents=[shared], help="Search catalog (+ live boards when reachable)"
    )
    search.add_argument("--query", default="", help="Keywords (defaults to saved target role)")
    search.add_argument("--no-live", action="store_true", help="Skip live job APIs")
    search.add_argument("--limit", type=int, default=10)

    sub.add_parser("status", parents=[shared], help="Show saved profile and applications")

    prepare = sub.add_parser(
        "prepare", parents=[shared], help="Draft an application packet for a job id"
    )
    prepare.add_argument("job_id")

    apply = sub.add_parser(
        "apply",
        parents=[shared],
        help="Mark an application applied after you submit off-site",
    )
    apply.add_argument("application_id", type=int)
    apply.add_argument("--confirm", action="store_true", help="Required. Refuses without this flag.")
    apply.add_argument("--notes", default="")

    paste = sub.add_parser("paste-job", parents=[shared], help="Add a job from JSON file")
    paste.add_argument("json_path")

    serve = sub.add_parser("serve", parents=[shared], help="Run the local hiring desk UI")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    desk = HiringDesk(db_path=args.db)
    try:
        if args.command == "review":
            path = Path(args.resume)
            payload = path.read_bytes()
            result = desk.ingest_resume_bytes(
                filename=path.name,
                payload=payload,
                target_role=args.role,
                target_location=args.location,
                remote_only=not args.onsite,
            )
            review = result["review"]
            resume = result["resume"]
            print(f"Candidate: {resume.get('name')}")
            print(f"ATS-style score: {review['overall']}/100")
            if review.get("recruiter_score") is not None:
                print(f"LLM recruiter score: {review['recruiter_score']}")
            print("Findings:")
            for finding in review["findings"]:
                print(f"  [{finding['severity']}] {finding['title']}: {finding['detail']}")
            print("Improvements:")
            for item in review["improvements"]:
                print(f"  - {item}")
            return 0
        if args.command == "search":
            result = desk.search(query=args.query, include_live=not args.no_live)
            jobs = result["jobs"][: args.limit]
            print(
                f"{result['count']} jobs (live fetched: {result['live_count']}; "
                f"skipped: {', '.join(result['skipped_sources']) or 'none'})"
            )
            for job in jobs:
                fit = job.get("fit") or {}
                score = fit.get("score")
                score_label = f"{score:>3}" if score is not None else "  -"
                print(f"[{score_label}] {job['id']}  {job['title']} @ {job['company']}")
            return 0
        if args.command == "status":
            _print_json(desk.status())
            return 0
        if args.command == "prepare":
            application = desk.prepare(args.job_id)
            print(f"Draft application #{application['id']} for {application['job_id']}")
            print(application["packet"]["cover_letter"])
            print("\nApply URL:", application["job"].get("apply_url"))
            return 0
        if args.command == "apply":
            application = desk.apply(args.application_id, confirm=args.confirm, notes=args.notes)
            print(f"Marked applied: #{application['id']} {application['job_id']}")
            print("Open:", application["job"].get("apply_url"))
            return 0
        if args.command == "paste-job":
            payload = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
            _print_json(desk.paste_job(payload))
            return 0
        if args.command == "serve":
            from job_agent.server import serve_forever

            desk.close()
            serve_forever(host=args.host, port=args.port, db_path=args.db)
            return 0
        parser.error("unknown command")
        return 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if args.command != "serve":
            desk.close()


if __name__ == "__main__":
    raise SystemExit(main())
