# Data dictionary (core objects)

Timestamp convention: source fields are naive wall-clock (`dd/mm/YYYY HH:MM`); original timezone unknown. Ingestion/publication times are UTC timestamptz.

## raw.incident_rows
Grain: one source CSV row per `(batch_id, file_row_number)`. Business fields stored as text.

## staging.incident_events
Grain: one accepted typed event. Invalid optional timestamps nulled with quality warnings.

## marts.fact_tickets
Grain: one incident per `source_track`. Retrospective summary — not an opening-time feature source.

## marts.ticket_open_features
Grain: one first-observed allowlisted snapshot per incident. Excludes outcome fields.

## marts.daily_volume
Grain: one opening date per track. `coverage_status=observed` means measured openings that day, not institutional total demand.

## marts.daily_backlog
Observed cumulative openings−closures proxy with `completeness_flag=observed_incomplete_prehistory`.

## marts.resolution_stats
Period/category/priority/group duration summaries with `n_eligible` and `n_missing_outcome` denominators.

## models.*
Registry, evaluations, forecast predictions, SLA source-flag scores (not verified breach).

## ops.export_releases
One validated multi-file CSV release; `is_latest_good` marks the Tableau candidate bundle.
