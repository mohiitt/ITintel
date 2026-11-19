# Pipeline guide

## Stages

1. **Discover / ingest** — local or S3 adapter → `raw.incident_rows` + `ops.ingestion_batches` (checksum idempotency)
2. **Validate** — rule catalog → `staging.incident_events` / `quarantine.*` / `ops.dq_*`
3. **Marts** — `marts.fact_tickets`, open features, state history, daily volume/backlog, resolution stats
4. **Forecast** — synthetic campus track (primary); seasonal naive baseline vs MA / ETS
5. **SLA source-flag** — opening allowlist features → latest `made_sla` (not verified breach)
6. **Export** — versioned CSV bundle + `ops.export_releases` + `LATEST_GOOD`

## Commands

```bash
itintel migrate
itintel ingest data/raw/incident_event_log.csv --track public_historical
itintel validate --track public_historical --force
itintel marts --track public_historical
itintel forecast
itintel sla --track public_historical
itintel eda --track public_historical
itintel export
# or all at once:
itintel run --track public_historical
```

## Retry / idempotency

- Same file checksum → `skipped_no_new_data`
- Validation can be re-forced with `--force`
- Marts recompute per source track
- Export never replaces `LATEST_GOOD` until the new bundle is complete
- Overlapping `itintel run` is rejected via advisory lock

## Source tracks

`public_historical` | `historical_replay` | `synthetic_quality` | `synthetic_campus`

Do not combine tracks in unlabeled KPIs.
