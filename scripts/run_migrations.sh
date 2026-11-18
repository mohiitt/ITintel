#!/bin/sh
# Apply versioned SQL migrations in order. Safe to re-run (IF NOT EXISTS DDL).
set -eu

MIGRATIONS_DIR="${MIGRATIONS_DIR:-/migrations}"

echo "Waiting for PostgreSQL at ${PGHOST:-localhost}..."
i=0
until pg_isready -h "${PGHOST:-localhost}" -U "${PGUSER:-itintel}" -d "${PGDATABASE:-itintel}" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "PostgreSQL not ready" >&2
    exit 1
  fi
  sleep 1
done

psql -v ON_ERROR_STOP=1 <<'SQL'
CREATE SCHEMA IF NOT EXISTS ops;
CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    version       TEXT PRIMARY KEY,
    applied_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum      TEXT,
    description   TEXT
);
SQL

for f in $(ls "$MIGRATIONS_DIR"/*.sql | sort); do
  version=$(basename "$f" .sql)
  already=$(psql -Atc "SELECT 1 FROM ops.schema_migrations WHERE version = '$version'" || true)
  if [ "$already" = "1" ]; then
    echo "Skip $version (already applied)"
    continue
  fi
  echo "Apply $version"
  psql -v ON_ERROR_STOP=1 -f "$f"
  psql -v ON_ERROR_STOP=1 -c \
    "INSERT INTO ops.schema_migrations (version, description) VALUES ('$version', 'applied by run_migrations.sh')"
done

echo "Migrations complete."
