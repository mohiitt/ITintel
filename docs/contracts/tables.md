# Table contracts

Grain, keys, and provenance for database objects. Schema DDL lives in `sql/migrations/`.

Source-track values: `public_historical` | `historical_replay` | `synthetic_quality` | `synthetic_campus`.

## raw.incident_rows

| Item | Contract |
| --- | --- |
| Grain | One source row per `(batch_id, file_row_number)` |
| Keys | `batch_id` + `file_row_number` |
| Business fields | Stored as **text** as received |
| Provenance | `batch_id`, content fingerprint, `loaded_at` |
| Notes | Retained even if later stages reject the row |

## ops.ingestion_batches

| Item | Contract |
| --- | --- |
| Grain | One processing attempt |
| Keys | `batch_id` (UUID) |
| Required | `source_track`, checksum, object identity, state, counts, timestamps |
| States | discovered, loading, loaded, validating, transformed, exported, failed, skipped_no_new_data |

## staging.incident_events

| Item | Contract |
| --- | --- |
| Grain | One canonical observed event/snapshot |
| Keys | Deterministic event identity + `source_track` |
| Fields | Parsed typed columns; invalid optional fields nulled with quality issues logged |
| Provenance | Links to `batch_id` / raw row |

## quarantine.incident_rows / quarantine.row_violations

| Item | Contract |
| --- | --- |
| Grain | One rejected raw row; one violation per (row, rule) |
| Notes | Violation count may exceed quarantined rows; dashboards use distinct raw-row identity |

## ops.dq_runs / ops.dq_check_results / ops.row_quality_issues

Batch-level quality summary, per-check results, and nonfatal row warnings for accepted rows.

## marts.fact_tickets

| Item | Contract |
| --- | --- |
| Grain | One incident per `source_track` |
| Role | Retrospective summary — **not** an opening-time feature source |
| Uniqueness | `(source_track, incident_number)` |

## marts.ticket_open_features

| Item | Contract |
| --- | --- |
| Grain | One eligible opening-time / first-observed feature snapshot per incident |
| Allowlist | See Phase 0 report; must not inherit future outcomes from `fact_tickets` |

## marts.ticket_state_history

Observed state intervals for historical operational views (supports reopens).

## marts.daily_volume / marts.daily_backlog / marts.resolution_stats

Daily arrivals, observed backlog with completeness flags, and period/category/priority/group duration summaries with denominators.

## models.*

Model registry, evaluation results, forecast predictions, SLA risk predictions — versioned with dataset, feature contract, and selection status.

## ops.export_releases

One validated multi-file release and publication status. Partial failures must not replace the last good release.
