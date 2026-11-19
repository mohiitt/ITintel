# Deployment / recovery guide

## Local (working now)
- Compose Postgres + Python venv
- `itintel migrate` / `itintel run`
- Advisory lock prevents overlapping mutation runs
- Export `LATEST_GOOD` pointer only updated after complete bundle

## Restore sketch
1. Stop pipeline/scheduler
2. Restore Postgres volume / dump
3. Reconcile `ops.ingestion_batches` checksums before re-ingest
4. Rebuild marts/export from staging without retraining if artifacts preserved

## AWS (blocked)
Needs your AWS account: EC2 + private S3 + instance role + Secrets Manager + Session Manager.
See `deploy/README.md`. Do not open port 5432 publicly.
