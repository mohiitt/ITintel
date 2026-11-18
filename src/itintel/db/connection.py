"""PostgreSQL connectivity via Psycopg 3 — never log passwords."""

from __future__ import annotations

import psycopg

from itintel.config import AppConfig, DatabaseConfig, load_config


def connect(database: DatabaseConfig | None = None) -> psycopg.Connection:
    cfg = database or load_config().database
    if not cfg.password:
        raise RuntimeError(
            "POSTGRES_PASSWORD is not set. Copy .env.example to .env before connecting."
        )
    return psycopg.connect(cfg.dsn)


def smoke_test(config: AppConfig | None = None) -> dict:
    """Verify connectivity and report schema readiness without exposing secrets."""
    cfg = config or load_config()
    with connect(cfg.database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, version()")
            dbname, user, version = cur.fetchone()
            cur.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name = ANY(%s)
                ORDER BY 1
                """,
                (["raw", "staging", "quarantine", "marts", "models", "ops"],),
            )
            schemas = [r[0] for r in cur.fetchall()]
            cur.execute(
                """
                SELECT version
                FROM ops.schema_migrations
                ORDER BY version
                """
            )
            migrations = [r[0] for r in cur.fetchall()]

    return {
        "ok": True,
        "database": dbname,
        "user": user,
        "server_version_prefix": version.split(",")[0],
        "endpoint": cfg.database.safe_summary(),
        "schemas": schemas,
        "migrations_applied": migrations,
    }
