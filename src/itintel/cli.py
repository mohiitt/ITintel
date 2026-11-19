"""Command-line entry points for local development."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="itintel", description="IT Service Desk Intelligence")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("smoke-db", help="Database connection and schema readiness check")
    sub.add_parser("migrate", help="Apply pending SQL migrations")

    p_discover = sub.add_parser("discover", help="List source objects via the configured adapter")
    p_discover.add_argument("--track", default=None)

    p_ingest = sub.add_parser("ingest", help="Ingest a local CSV/ZIP into raw.incident_rows")
    p_ingest.add_argument("path", nargs="?", default=None)
    p_ingest.add_argument("--track", default=None)
    p_ingest.add_argument("--force", action="store_true")

    p_validate = sub.add_parser("validate", help="Validate a raw batch into staging/quarantine")
    p_validate.add_argument("batch_id", nargs="?", default=None)
    p_validate.add_argument("--track", default="public_historical")
    p_validate.add_argument("--force", action="store_true")

    p_marts = sub.add_parser("marts", help="Rebuild analytical marts for a source track")
    p_marts.add_argument("--track", default="public_historical")

    p_forecast = sub.add_parser("forecast", help="Run synthetic campus forecast experiment")
    p_forecast.add_argument("--track", default="synthetic_campus")

    p_sla = sub.add_parser("sla", help="Run source-flag SLA experiment (polarity unresolved)")
    p_sla.add_argument("--track", default="public_historical")

    sub.add_parser("export", help="Build versioned CSV release bundle")

    p_run = sub.add_parser("run", help="Run ingest→validate→marts→models→export pipeline")
    p_run.add_argument("--path", default=None, help="Optional ingest path")
    p_run.add_argument("--track", default="public_historical")
    p_run.add_argument("--skip-models", action="store_true")

    p_eda = sub.add_parser("eda", help="Write Phase 6 EDA report and charts")
    p_eda.add_argument("--track", default="public_historical")

    args = parser.parse_args(argv)

    if args.command == "smoke-db":
        from itintel.db import smoke_test

        print(json.dumps(smoke_test(), indent=2))
        return 0

    if args.command == "migrate":
        from itintel.db import apply_migrations

        print(json.dumps({"applied": apply_migrations()}, indent=2))
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
        print(
            json.dumps(
                [
                    {
                        "display_name": o.display_name,
                        "uri": o.uri,
                        "content_sha256": o.content_sha256,
                        "size_bytes": o.size_bytes,
                        "source_track": o.source_track,
                    }
                    for o in objects
                ],
                indent=2,
            )
        )
        return 0

    if args.command == "ingest":
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

    if args.command == "validate":
        from itintel.config import load_config
        from itintel.db.connection import connect
        from itintel.validation.validate_batch import validate_batch

        cfg = load_config()
        batch_id = args.batch_id
        if not batch_id:
            with connect(cfg.database) as conn:
                row = conn.execute(
                    """
                    SELECT batch_id FROM ops.ingestion_batches
                    WHERE source_track = %s
                    ORDER BY started_at DESC LIMIT 1
                    """,
                    (args.track,),
                ).fetchone()
            if not row:
                print(json.dumps({"error": "no batch found"}))
                return 1
            batch_id = str(row[0])
        result = validate_batch(batch_id, config=cfg, force=args.force)
        print(
            json.dumps(
                {
                    "batch_id": result.batch_id,
                    "dq_run_id": result.dq_run_id,
                    "status": result.status,
                    "rows_checked": result.rows_checked,
                    "rows_accepted": result.rows_accepted,
                    "rows_quarantined": result.rows_quarantined,
                    "warning_count": result.warning_count,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "marts":
        from itintel.transforms.marts import build_marts

        result = build_marts(args.track)
        print(
            json.dumps(
                {
                    "source_track": result.source_track,
                    "ticket_count": result.ticket_count,
                    "daily_volume_days": result.daily_volume_days,
                    "open_feature_count": result.open_feature_count,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "forecast":
        from itintel.training.forecast import run_forecast_experiment

        result = run_forecast_experiment(source_track=args.track)
        print(
            json.dumps(
                {
                    "model_version": result.model_version,
                    "selected_model": result.selected_model,
                    "n_evals": len(result.evaluations),
                    "next_seven": result.next_seven,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "sla":
        from itintel.training.sla_risk import run_sla_experiment

        result = run_sla_experiment(source_track=args.track, force=True)
        print(
            json.dumps(
                {
                    "model_version": result.model_version,
                    "status": result.status,
                    "polarity_status": result.polarity_status,
                    "n_rows": result.n_rows,
                    "prevalence": result.prevalence,
                    "average_precision": result.average_precision,
                    "threshold": result.threshold,
                    "test_precision": result.test_precision,
                    "test_recall": result.test_recall,
                    "notes": result.notes,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "export":
        from itintel.export.release import build_export_release

        result = build_export_release()
        print(
            json.dumps(
                {
                    "release_id": result.release_id,
                    "status": result.status,
                    "path": result.path,
                    "files": result.files,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "run":
        from itintel.pipeline import run_pipeline

        result = run_pipeline(
            ingest_path=Path(args.path) if args.path else None,
            source_track=args.track,
            skip_models=args.skip_models,
        )
        print(json.dumps({"ok": result.ok, "stages": result.stages}, indent=2, default=str))
        return 0 if result.ok else 1

    if args.command == "eda":
        from itintel.transforms.eda import write_eda_report

        path = write_eda_report(source_track=args.track)
        print(json.dumps({"report": str(path)}, indent=2))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
