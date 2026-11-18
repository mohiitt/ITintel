# ADR 0001 — Forecast track and SLA gate decisions

**Status:** Accepted  
**Date:** 2026-11-18  
**Context:** Phase 0 source verification of the UCI Incident Management Process Enriched Event Log.

## Decision

1. **Primary forecast track = synthetic campus scenarios.** Real opening-date coverage is concentrated in March–May 2016 (~98.1% of incidents). Do not claim full-year or academic-calendar demand learning from this source by default.
2. **Optional secondary:** a clearly labeled March–May 2016 real-data forecasting *feasibility* experiment may be added later; every export and dashboard view must disclose the restricted window and coverage limits.
3. **SLA classification remains CONDITIONAL.** UCI prose describes `made_sla` as whether the incident *exceeded* the target SLA, while the column name suggests attainment. Polarity is not inferred from the name. Descriptive use of the raw flag is allowed; a "breach" model requires a documented polarity + maturity policy first.
4. **Creation-time features are restricted.** Earliest audit rows commonly contain `closed_at` / `resolved_at`. Opening-feature tables must use an explicit allowlist and must not inherit retrospective outcomes.
5. **Source tracks stay separated** everywhere: `public_historical`, `historical_replay`, `synthetic_quality`, `synthetic_campus`.

## Consequences

- Resume and dashboard wording must distinguish synthetic forecasting from measured historical demand.
- Pipeline configuration defaults `forecast.source_track` to `synthetic_campus`.
- SLA risk training is gated behind `models.sla.enabled` until polarity is resolved in a follow-up ADR.

## Evidence

See `docs/reports/phase0_feasibility_report.md` and `data/profiles/source_profile.json`.
