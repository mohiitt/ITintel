# Insights memo

Audience: IT service manager. Source track: `public_historical` unless noted.

## Finding 1 — Coverage concentration
**Observation:** Almost all openings fall in March–May 2016.  
**Measure:** 24,437 / 24,918 incidents (98.1%) open in that window; later months have tens of openings, not routine demand.  
**Alternative:** Export truncation / regime change, not a true summer collapse.  
**Next step:** Report observed demand only; keep synthetic forecast separately labeled.

## Finding 2 — Reopens are common enough to matter for backlog
**Observation:** Reopen signals appear on a meaningful share of incidents.  
**Measure:** See Phase 6 EDA `reopen_observed` rate on `marts.fact_tickets`.  
**Alternative:** Field may be enriched/backfilled; not proof of agent quality issues.  
**Next step:** Use state-history intervals for backlog views; avoid single open→resolve assumptions.

## Finding 3 — Resolution tails differ by slice
**Observation:** p90 time-to-first-resolution varies widely by category/priority/group.  
**Measure:** Exported in `bottlenecks.csv` with `n_eligible` denominators.  
**Alternative:** Ownership snapshots and case mix differ; not causal team ranking.  
**Next step:** Investigate top slices with sample sizes visible; do not average category medians into a fake overall median.

## Forecast note
Synthetic campus seasonal-naive remains the selected forecast in the latest run. Useful for demonstrating evaluation discipline; not SJSU demand.
