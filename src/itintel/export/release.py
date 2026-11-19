"""Versioned CSV export releases for Tableau (Phase 9)."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from itintel.config import AppConfig, load_config
from itintel.db.connection import connect


@dataclass(frozen=True)
class ReleaseResult:
    release_id: str
    status: str
    path: str
    files: list[str]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_sql_df(conn, sql: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


def build_export_release(
    *,
    source_tracks: list[str] | None = None,
    config: AppConfig | None = None,
) -> ReleaseResult:
    cfg = config or load_config()
    tracks = source_tracks or ["public_historical", "synthetic_campus"]
    release_id = str(uuid.uuid4())
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(cfg.export_dir) / f"release_{ts}_{release_id[:8]}"
    staging_dir = out_dir / "_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    files_meta: dict[str, dict] = {}
    row_counts: dict[str, int] = {}

    with connect(cfg.database) as conn:
        # overview_daily
        overview = _read_sql_df(
            conn,
            """
            SELECT v.source_track, v.arrival_date,
                   v.distinct_arrivals,
                   b.observed_backlog,
                   b.completeness_flag
            FROM marts.daily_volume v
            LEFT JOIN marts.daily_backlog b
              ON b.source_track = v.source_track AND b.as_of_date = v.arrival_date
            WHERE v.source_track = ANY(%s)
            ORDER BY v.source_track, v.arrival_date
            """,
            (tracks,),
        )
        # bottlenecks
        bottlenecks = _read_sql_df(
            conn,
            """
            SELECT * FROM marts.resolution_stats
            WHERE source_track = ANY(%s)
            ORDER BY source_track, category, priority
            """,
            (tracks,),
        )
        # forecast evaluation
        forecast_eval = _read_sql_df(
            conn,
            """
            SELECT e.model_version, e.fold_id, e.horizon_days, e.metric_name,
                   e.metric_value, e.details_json, r.source_track, r.selection_status
            FROM models.evaluation_results e
            JOIN models.model_registry r ON r.model_version = e.model_version
            WHERE r.model_family = 'forecast'
            ORDER BY e.evaluation_id
            """,
        )
        forecast_next = _read_sql_df(
            conn,
            """
            SELECT p.*
            FROM models.forecast_predictions p
            JOIN models.model_registry r ON r.model_version = p.model_version
            WHERE r.selection_status = 'selected' AND r.model_family = 'forecast'
            ORDER BY p.target_date
            """,
        )
        ticket_risk = _read_sql_df(
            conn,
            """
            SELECT p.model_version, p.source_track, p.incident_number, p.feature_cutoff,
                   p.score, p.threshold, p.compatible, p.scored_at,
                   'source_flag_not_verified_breach' AS score_semantics
            FROM models.sla_risk_predictions p
            JOIN models.model_registry r ON r.model_version = p.model_version
            ORDER BY p.scored_at DESC
            LIMIT 5000
            """,
        )
        data_quality = _read_sql_df(
            conn,
            """
            SELECT c.dq_run_id, r.batch_id, r.source_track, r.status AS dq_status,
                   c.rule_id, c.rule_version, c.status AS check_status,
                   c.rows_checked, c.failure_count, c.distinct_affected, c.details
            FROM ops.dq_check_results c
            JOIN ops.dq_runs r ON r.dq_run_id = c.dq_run_id
            ORDER BY c.check_result_id DESC
            LIMIT 10000
            """,
        )
        # freshness
        freshness = _read_sql_df(
            conn,
            """
            SELECT source_track, state, content_sha256, row_count, accepted_count,
                   quarantined_count, started_at, finished_at, updated_at
            FROM ops.ingestion_batches
            ORDER BY started_at DESC
            LIMIT 50
            """,
        )

    frames = {
        "overview_daily.csv": overview,
        "bottlenecks.csv": bottlenecks,
        "forecast_evaluation.csv": forecast_eval,
        "forecast_next_seven_days.csv": forecast_next,
        "ticket_risk.csv": ticket_risk,
        "data_quality.csv": data_quality,
        "freshness.csv": freshness,
    }

    for name, df in frames.items():
        path = staging_dir / name
        df.to_csv(path, index=False)
        row_counts[name] = int(len(df))
        files_meta[name] = {
            "sha256": _sha256(path),
            "rows": row_counts[name],
            "columns": list(df.columns),
        }

    manifest = {
        "release_id": release_id,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_tracks": tracks,
        "status": "complete",
        "files": files_meta,
        "row_counts": row_counts,
        "notes": [
            "Tableau Public refresh is a separate manual operation.",
            "synthetic_campus forecasts are not measured SJSU demand.",
            "ticket_risk scores are source-flag predictions; made_sla polarity unresolved.",
        ],
    }
    manifest_path = staging_dir / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    files_meta["release_manifest.json"] = {
        "sha256": _sha256(manifest_path),
        "rows": None,
        "columns": None,
    }

    # Promote staging → final
    for p in staging_dir.iterdir():
        shutil.move(str(p), str(out_dir / p.name))
    staging_dir.rmdir()

    # latest-good pointer
    latest = Path(cfg.export_dir) / "LATEST_GOOD"
    latest.write_text(out_dir.name + "\n")

    with connect(cfg.database) as conn:
        # clear previous latest-good flags
        conn.execute("UPDATE ops.export_releases SET is_latest_good = FALSE WHERE is_latest_good")
        conn.execute(
            """
            INSERT INTO ops.export_releases (
                release_id, source_tracks, status, manifest_uri, row_counts_json,
                checksums_json, is_latest_good, generated_at
            ) VALUES (%s, %s, 'complete', %s, %s::jsonb, %s::jsonb, TRUE, %s)
            """,
            (
                release_id,
                tracks,
                str(out_dir / "release_manifest.json"),
                json.dumps(row_counts),
                json.dumps({k: v["sha256"] for k, v in files_meta.items()}),
                datetime.now(UTC),
            ),
        )
        # mark batches exported
        conn.execute(
            """
            UPDATE ops.ingestion_batches
            SET state = 'exported', updated_at = %s
            WHERE state = 'transformed' AND source_track = ANY(%s)
            """,
            (datetime.now(UTC), tracks),
        )
        conn.commit()

    return ReleaseResult(
        release_id=release_id,
        status="complete",
        path=str(out_dir),
        files=list(files_meta.keys()),
    )
