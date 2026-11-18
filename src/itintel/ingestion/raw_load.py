"""Phase 3 — raw ingestion and batch tracking with checksum idempotency."""

from __future__ import annotations

import csv
import io
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from itintel.common import RAW_COLUMN_NAMES
from itintel.config import AppConfig, load_config
from itintel.db.connection import connect
from itintel.ingestion.adapters import DiscoveredObject, LocalFileAdapter, sha256_bytes

REQUIRED_COLUMNS = ("number", "opened_at", "sys_updated_at")


@dataclass(frozen=True)
class LoadResult:
    batch_id: str
    state: str
    row_count: int
    content_sha256: str
    message: str


def _resolve_csv_text(path: Path) -> tuple[str, str]:
    """Return (csv_text, content_sha256) for a CSV or ZIP containing one CSV."""
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError(f"Expected exactly one CSV in ZIP, found {names}")
            text = zf.read(names[0]).decode("utf-8")
        return text, digest
    return raw.decode("utf-8"), digest


def _fingerprint_row(row: dict[str, str]) -> str:
    payload = "\x1f".join(row.get(c, "") for c in RAW_COLUMN_NAMES)
    return sha256_bytes(payload.encode("utf-8"))


def ingest_local_file(
    path: Path,
    *,
    source_track: str | None = None,
    config: AppConfig | None = None,
    force: bool = False,
) -> LoadResult:
    """Load a CSV/ZIP into raw.incident_rows as a tracked batch.

    Duplicate content checksums of previously successful loads are skipped
    unless force=True.
    """
    cfg = config or load_config()
    track = source_track or cfg.source_track
    path = Path(path)
    csv_text, content_sha = _resolve_csv_text(path)
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header")
    header = [h.strip() for h in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    batch_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    with connect(cfg.database) as conn:
        # Idempotency: successful prior load with same checksum.
        prior = conn.execute(
            """
            SELECT batch_id, state, row_count
            FROM ops.ingestion_batches
            WHERE content_sha256 = %s
              AND source_track = %s
              AND state IN ('loaded', 'validating', 'transformed', 'exported')
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (content_sha, track),
        ).fetchone()
        if prior and not force:
            return LoadResult(
                batch_id=str(prior[0]),
                state="skipped_no_new_data",
                row_count=int(prior[2] or 0),
                content_sha256=content_sha,
                message=f"Duplicate checksum already loaded as batch {prior[0]}",
            )

        conn.execute(
            """
            INSERT INTO ops.ingestion_batches (
                batch_id, source_track, object_path, content_sha256,
                state, started_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 'loading', %s, %s, %s)
            """,
            (batch_id, track, str(path.resolve()), content_sha, now, now, now),
        )

        rows_out: list[tuple] = []
        for i, raw_row in enumerate(reader, start=1):
            normalized = {c: (raw_row.get(c) or "") for c in RAW_COLUMN_NAMES}
            fp = _fingerprint_row(normalized)
            rows_out.append(
                (
                    batch_id,
                    i,
                    fp,
                    now,
                    *[normalized[c] for c in RAW_COLUMN_NAMES],
                )
            )

        cols = ["batch_id", "file_row_number", "content_fingerprint", "loaded_at", *RAW_COLUMN_NAMES]
        cols_sql = ", ".join(cols)
        with conn.cursor() as cur:
            with cur.copy(f"COPY raw.incident_rows ({cols_sql}) FROM STDIN") as copy:
                for row in rows_out:
                    copy.write_row(row)

        finished = datetime.now(UTC)
        conn.execute(
            """
            UPDATE ops.ingestion_batches
            SET state = 'loaded',
                row_count = %s,
                finished_at = %s,
                updated_at = %s
            WHERE batch_id = %s
            """,
            (len(rows_out), finished, finished, batch_id),
        )
        conn.commit()

    return LoadResult(
        batch_id=batch_id,
        state="loaded",
        row_count=len(rows_out),
        content_sha256=content_sha,
        message=f"Loaded {len(rows_out)} rows from {path.name}",
    )


def discover_and_load_new(config: AppConfig | None = None) -> list[LoadResult]:
    """Discover local CSV/ZIP objects and load any new checksums."""
    cfg = config or load_config()
    adapter = LocalFileAdapter(cfg.local_source_dir)
    results: list[LoadResult] = []
    for obj in adapter.list_objects(cfg.source_track):
        # Prefer CSV over ZIP when both represent the same extract.
        if obj.display_name.endswith(".zip"):
            continue
        path = Path(obj.uri.removeprefix("file://"))
        results.append(ingest_local_file(path, source_track=obj.source_track, config=cfg))
    return results


def describe_object(obj: DiscoveredObject) -> dict:
    return {
        "display_name": obj.display_name,
        "content_sha256": obj.content_sha256,
        "size_bytes": obj.size_bytes,
        "source_track": obj.source_track,
    }
