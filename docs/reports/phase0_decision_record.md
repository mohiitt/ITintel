# Phase 0 decision record

**Date:** 2026-11-18  
**Inputs:** Fresh UCI ZIP download + independent CSV profile (`scripts/phase0_profile_source.py`).

## Integrity

| Artifact | SHA-256 |
| --- | --- |
| ZIP | `6294e29a311647306bfdfc85783f7df66517c197b9cd49aa5ee36ba9c525d1d6` |
| CSV | `fd184bbfd62329cfe093e99da2ea7071905f2ead91900b448eb2635870821bef` |

Matches the planning-time inspection.

## Selected paths

1. **Forecast:** synthetic campus primary (`forecast.primary_track = synthetic_campus`).
2. **SLA:** keep raw `made_sla`; `sla.enabled = false` until polarity ADR.
3. **Descriptive analytics:** proceed on `public_historical`.
4. **Tableau publication gate:** deferred to Phase 11 (CSV route assumed; not verified this session).

## Resume wording implications

- Do **not** claim full-year ticket-demand forecasting from the public log.
- Do **not** claim SLA-breach prediction until polarity + maturity policy are closed.
- Prefer: “built a reproducible IT service-desk analytics pipeline with quality checks, synthetic forecast demonstration, and Tableau exports.”

See also ADR 0001.
