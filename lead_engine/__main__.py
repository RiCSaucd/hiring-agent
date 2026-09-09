"""CLI: hunt First Coast leads, run the 8-gate pipeline, and serve the desk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lead_engine.service import DEFAULT_DB, NexusDesk


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path for the local lead ledger")

    parser = argparse.ArgumentParser(
        prog="python -m lead_engine",
        description="Nexus Lead Engine — hunt, score, and deliver First Coast property leads.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    hunt = sub.add_parser("hunt", parents=[shared], help="Search the bundled Firecrawl + RocketReach set")
    hunt.add_argument("--query", default="", help="Keywords")
    hunt.add_argument("--title", default="Property Manager")
    hunt.add_argument("--location", default="Jacksonville")
    hunt.add_argument("--import-all", action="store_true", help="Import every hit into the ledger")

    sub.add_parser("status", parents=[shared], help="Show lead counts and pipeline gates")

    pipe = sub.add_parser("pipeline", parents=[shared], help="Run the 8-gate score/verify pipeline")
    pipe.add_argument("--ids", nargs="*", default=None, help="Optional lead ids")

    export = sub.add_parser("export", parents=[shared], help="Write CSV to stdout")
    export.add_argument("--safe-only", action="store_true", help="Only verified-valid emails")

    csv_cmd = sub.add_parser("import-csv", parents=[shared], help="Import prospects from a CSV file")
    csv_cmd.add_argument("path")

    scrape = sub.add_parser("scrape", parents=[shared], help="Extract printed contacts from a company URL")
    scrape.add_argument("url")

    deliver = sub.add_parser("deliver", parents=[shared], help="Mark leads delivered to a client pack")
    deliver.add_argument("client")
    deliver.add_argument("--ids", nargs="+", required=True)

    sub.add_parser("reset", parents=[shared], help="Reset the demo ledger")

    serve = sub.add_parser("serve", parents=[shared], help="Run the local Nexus desk UI")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8770)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    desk = NexusDesk(db_path=args.db)
    try:
        if args.command == "hunt":
            result = desk.hunt(query=args.query, title=args.title, location=args.location)
            print(f"{result['count']} targets · {result['title']} · {result['location']}")
            for hit in result["hits"]:
                email = hit.get("email") or "(no printed email)"
                print(f"  {hit['id']:18} {hit['full_name']:28} {hit['company']}  {email}")
            if args.import_all:
                imported = desk.import_hits([hit["id"] for hit in result["hits"]])
                print(f"Imported {imported['created']} · merged {imported['updated']}")
            return 0
        if args.command == "status":
            _print_json(desk.status())
            return 0
        if args.command == "pipeline":
            result = desk.run_pipeline(args.ids)
            print(f"Scored {result['updated']} · dropped {result['invalid']} · hot {len(result['hot_ids'])}")
            return 0
        if args.command == "export":
            sys.stdout.write(desk.export_csv(safe_only=args.safe_only))
            return 0
        if args.command == "import-csv":
            text = Path(args.path).read_text(encoding="utf-8")
            result = desk.import_csv(text)
            print(f"Imported {result['created']} · merged {result['updated']}")
            return 0
        if args.command == "scrape":
            _print_json(desk.enrich_url(args.url))
            return 0
        if args.command == "deliver":
            result = desk.deliver(args.ids, client_name=args.client)
            print(f"Delivered batch {result['batch']['id']} to {args.client}")
            return 0
        if args.command == "reset":
            _print_json(desk.reset_demo())
            return 0
        if args.command == "serve":
            from lead_engine.server import serve_forever

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
