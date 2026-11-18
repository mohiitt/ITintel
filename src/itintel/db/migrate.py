"""Apply versioned SQL migrations from sql/migrations/."""

from __future__ import annotations

import hashlib
from pathlib import Path

from itintel.config import ROOT, load_config
from itintel.db.connection import connect

DEFAULT_MIGRATIONS = ROOT / "sql" / "migrations"


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_migrations(migrations_dir: Path | None = None) -> list[str]:
    directory = migrations_dir or DEFAULT_MIGRATIONS
    files = sorted(directory.glob("*.sql"))
    applied: list[str] = []

    cfg = load_config()
    with connect(cfg.database) as conn:
        conn.execute(
            """
            CREATE SCHEMA IF NOT EXISTS ops;
            CREATE TABLE IF NOT EXISTS ops.schema_migrations (
                version       TEXT PRIMARY KEY,
                applied_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                checksum      TEXT,
                description   TEXT
            );
            """
        )
        conn.commit()

        for path in files:
            version = path.stem
            row = conn.execute(
                "SELECT 1 FROM ops.schema_migrations WHERE version = %s",
                (version,),
            ).fetchone()
            if row:
                continue
            sql = path.read_text()
            conn.execute(sql)
            conn.execute(
                """
                INSERT INTO ops.schema_migrations (version, checksum, description)
                VALUES (%s, %s, %s)
                """,
                (version, _checksum(path), f"applied from {path.name}"),
            )
            conn.commit()
            applied.append(version)

    return applied
