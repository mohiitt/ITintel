"""End-to-end pipeline orchestration (Phases 3–9)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from itintel.config import AppConfig, load_config
from itintel.db.connection import connect
from itintel.export.release import build_export_release
from itintel.ingestion.raw_load import discover_and_load_new, ingest_local_file
from itintel.training.forecast import run_forecast_experiment
from itintel.training.sla_risk import run_sla_experiment
from itintel.transforms.marts import build_marts
from itintel.validation.validate_batch import validate_batch


@dataclass
class PipelineResult:
    stages: dict
    ok: bool


def run_pipeline(
    *,
    ingest_path: Path | None = None,
    source_track: str = "public_historical",
    skip_models: bool = False,
    config: AppConfig | None = None,
) -> PipelineResult:
    cfg = config or load_config()
    stages: dict = {}

    # Hold a dedicated session lock for the full run (session-level advisory lock).
    lock_conn = connect(cfg.database)
    try:
        got = lock_conn.execute("SELECT pg_try_advisory_lock(872341)").fetchone()[0]
        if not got:
            return PipelineResult(stages={"lock": "rejected_overlapping_run"}, ok=False)

        if ingest_path:
            load = ingest_local_file(ingest_path, source_track=source_track, config=cfg)
            stages["ingest"] = asdict(load)
            batch_ids = [load.batch_id] if load.state == "loaded" else []
        else:
            loads = discover_and_load_new(cfg)
            stages["ingest"] = [asdict(x) for x in loads]
            batch_ids = [x.batch_id for x in loads if x.state == "loaded"]

        if not batch_ids:
            with connect(cfg.database) as conn:
                row = conn.execute(
                    """
                    SELECT batch_id FROM ops.ingestion_batches
                    WHERE source_track = %s
                      AND state IN ('loaded', 'validating')
                    ORDER BY started_at DESC LIMIT 1
                    """,
                    (source_track,),
                ).fetchone()
            if row:
                batch_ids = [str(row[0])]

        # Also re-validate a transformed batch's sibling if nothing pending:
        # fall back to latest batch for track so marts can rebuild.
        if not batch_ids:
            with connect(cfg.database) as conn:
                row = conn.execute(
                    """
                    SELECT batch_id FROM ops.ingestion_batches
                    WHERE source_track = %s
                    ORDER BY started_at DESC LIMIT 1
                    """,
                    (source_track,),
                ).fetchone()
            if row:
                batch_ids = [str(row[0])]

        validate_results = []
        for bid in batch_ids:
            vr = validate_batch(bid, config=cfg)
            validate_results.append(asdict(vr))
        stages["validate"] = validate_results

        marts = build_marts(source_track, config=cfg)
        stages["marts"] = asdict(marts)

        if not skip_models:
            forecast = run_forecast_experiment(source_track="synthetic_campus", config=cfg)
            stages["forecast"] = {
                "model_version": forecast.model_version,
                "selected_model": forecast.selected_model,
                "n_evals": len(forecast.evaluations),
                "next_seven": forecast.next_seven,
            }
            sla = run_sla_experiment(source_track=source_track, config=cfg, force=True)
            stages["sla"] = asdict(sla)

        release = build_export_release(
            source_tracks=[source_track, "synthetic_campus"],
            config=cfg,
        )
        stages["export"] = asdict(release)
        return PipelineResult(stages=stages, ok=True)
    finally:
        try:
            lock_conn.execute("SELECT pg_advisory_unlock(872341)")
        finally:
            lock_conn.close()


def run_pipeline_json(**kwargs) -> str:
    result = run_pipeline(**kwargs)
    return json.dumps({"ok": result.ok, "stages": result.stages}, indent=2, default=str)
