"""Command-line entry points for local development."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="itintel", description="IT Service Desk Intelligence")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("smoke-db", help="Database connection and schema readiness check")
    sub.add_parser("migrate", help="Apply pending SQL migrations")
    p_discover = sub.add_parser("discover", help="List source objects via the configured adapter")
    p_discover.add_argument(
        "--track",
        default=None,
        help="Source track override (default from config)",
    )
    p_ingest = sub.add_parser("ingest", help="Ingest a local CSV/ZIP into raw.incident_rows")
    p_ingest.add_argument("path", nargs="?", default=None, help="File path (default: discover new)")
    p_ingest.add_argument("--track", default=None, help="Source track override")
    p_ingest.add_argument(
        "--force",
        action="store_true",
        help="Reload even if checksum was already loaded",
    )

    args = parser.parse_args(argv)

    if args.command == "smoke-db":
        from itintel.db import smoke_test

        result = smoke_test()
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.command == "migrate":
        from itintel.db import apply_migrations

        applied = apply_migrations()
        print(json.dumps({"applied": applied}, indent=2))
        return 0

    if args.command == "discover":
        from itintel.config import load_config
        from itintel.ingestion.adapters import build_adapter

        cfg = load_config()
        track = args.track or cfg.source_track
        adapter = build_adapter(
            local_dir=cfg.local_source_dir,
            s3_bucket=cfg.s3_bucket,
            s3_prefix=cfg.s3_prefix,
        )
        objects = adapter.list_objects(track)
        payload = [
            {
                "display_name": o.display_name,
                "uri": o.uri,
                "content_sha256": o.content_sha256,
                "size_bytes": o.size_bytes,
                "source_track": o.source_track,
            }
            for o in objects
        ]
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "ingest":
        from pathlib import Path

        from itintel.config import load_config
        from itintel.ingestion.raw_load import discover_and_load_new, ingest_local_file

        cfg = load_config()
        if args.path:
            result = ingest_local_file(
                Path(args.path),
                source_track=args.track,
                config=cfg,
                force=args.force,
            )
            print(
                json.dumps(
                    {
                        "batch_id": result.batch_id,
                        "state": result.state,
                        "row_count": result.row_count,
                        "content_sha256": result.content_sha256,
                        "message": result.message,
                    },
                    indent=2,
                )
            )
            return 0
        results = discover_and_load_new(cfg)
        print(
            json.dumps(
                [
                    {
                        "batch_id": r.batch_id,
                        "state": r.state,
                        "row_count": r.row_count,
                        "content_sha256": r.content_sha256,
                        "message": r.message,
                    }
                    for r in results
                ],
                indent=2,
            )
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
