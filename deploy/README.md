# Deployment notes

## Local Compose (implemented)

```bash
cp .env.example .env
docker compose up -d postgres
itintel migrate
itintel run --track public_historical
```

Postgres is published on **host port 5433** by default.

## Scheduler (Phase 10)

`deploy/crontab` is intended for a Supercronic service. Wire it after the pipeline image builds cleanly:

```yaml
# sketch — enable when image is ready
scheduler:
  image: itintel-pipeline:local
  depends_on: [postgres]
  volumes: [./deploy/crontab:/app/crontab:ro]
  command: ["supercronic", "/app/crontab"]
```

Overlapping runs are rejected via PostgreSQL advisory lock `872341`.

## AWS (Phase 12) — blocked on account access

Requires from you:
1. AWS account access (or confirmation to use a specific profile/region)
2. Permission to create EC2, S3 bucket, IAM instance role, Secrets Manager secret
3. Budget awareness (t3.small candidate; verify with Pricing Calculator)

Prepared but not executed:
- `Dockerfile` for the pipeline image
- Instance-role auth pattern (no static keys in repo)
- Private S3 prefixes for raw / releases / artifacts / backups
- Session Manager admin access (no public Postgres)

## Tableau Public (Phase 11) — done

Live workbook (3 staff dashboards; enable **Show Sheets** in viz Settings if tabs are missing):

https://public.tableau.com/app/profile/mohit.manoj.barade/viz/IT_Service_Desk_Intelligence/1ServiceOverview

Local package: `dashboard/IT_Service_Desk_Intelligence.twbx` (Hyper extracts). Rebuild with `python dashboard/build_tableau_workbook.py`. CSV releases remain under `data/releases/` via `LATEST_GOOD`.
