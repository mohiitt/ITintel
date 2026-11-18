"""Integration tests requiring a live PostgreSQL (Compose on port 5433)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from itintel.config import load_config
from itintel.db import apply_migrations, smoke_test
from itintel.db.connection import connect
from itintel.ingestion.fixtures import generate_quality_fixtures
from itintel.ingestion.raw_load import ingest_local_file

pytestmark = pytest.mark.skipif(
    os.environ.get("ITINTEL_SKIP_DB_TESTS") == "1",
    reason="ITINTEL_SKIP_DB_TESTS=1",
)


@pytest.fixture(scope="module")
def db_ready() -> None:
    try:
        apply_migrations()
        assert smoke_test()["ok"] is True
    except Exception as exc:  # noqa: BLE001 — surface skip when DB absent
        pytest.skip(f"PostgreSQL not available: {exc}")


def test_ingest_idempotent_on_checksum(tmp_path: Path, db_ready: None) -> None:
    import uuid

    fixtures = generate_quality_fixtures(tmp_path)
    path = next(p for p in fixtures if p.name == "valid_incident_update.csv")
    # Unique content so prior test runs / shared DB state cannot skip the first load.
    unique = path.read_text().replace("INC0000010", f"INC{uuid.uuid4().hex[:8].upper()}")
    path.write_text(unique)
    cfg = load_config()

    first = ingest_local_file(path, source_track="synthetic_quality", config=cfg)
    assert first.state == "loaded"
    assert first.row_count == 2

    second = ingest_local_file(path, source_track="synthetic_quality", config=cfg)
    assert second.state == "skipped_no_new_data"
    assert second.content_sha256 == first.content_sha256

    with connect(cfg.database) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM raw.incident_rows WHERE batch_id = %s",
            (first.batch_id,),
        ).fetchone()[0]
    assert count == 2
