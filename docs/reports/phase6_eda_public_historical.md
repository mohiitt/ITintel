# Phase 6 — Exploratory analysis (public_historical)

## Coverage

| Metric | Value |
| --- | ---: |
| Distinct incidents | 24,918 |
| Distinct opening dates | 207 |
| Reopen observed rate | 0.011036198731840436 |
| Latest made_sla counts | {True: 15803, False: 9115} |

DQ recent runs: [{'status': 'passed', 'rows_checked': 141712, 'rows_accepted': 141712, 'rows_quarantined': 0}]

Charts: `docs/reports/charts/arrivals_public_historical.png`, `docs/reports/charts/resolution_hours_public_historical.png`.

## Top opening categories

| Category | Incidents |
| --- | ---: |
| Category 42 | 3629 |
| Category 26 | 3268 |
| Category 53 | 2655 |
| Category 46 | 2243 |
| Category 32 | 1495 |
| Category 9 | 1141 |
| Category 37 | 1135 |
| Category 23 | 1071 |
| Category 20 | 1067 |
| Category 57 | 916 |

## Candidate findings

### Finding 1
- **Observation:** Arrival volume is highly concentrated in a short calendar window.
- **Measure:** Peak day 2016-03-07 had 607 openings; 207 distinct opening dates overall.
- **Alternative explanation:** Source export coverage may truncate later months rather than demand falling.
- **Follow-up:** Keep synthetic forecast track separate; label observed vs total demand.

### Finding 2
- **Observation:** A non-trivial share of incidents show an observed reopen signal.
- **Measure:** reopen_observed rate = 1.1% of 24,918 incidents.
- **Alternative explanation:** reopen_count may be backfilled; not proof of agent error.
- **Follow-up:** Use state-history intervals for backlog; avoid causal staffing claims.

### Finding 3
- **Observation:** Some category/priority/group slices have much longer p90 resolution times.
- **Measure:** Highest p90 in export: category=Category 55, priority=4 - Low, group=Group 33, p90_hours=7313.893333333333, n_eligible=17.
- **Alternative explanation:** Assignment group is ownership snapshot, not proven cause of delay.
- **Follow-up:** Investigate with denominators visible; do not average category medians.


## Model feasibility revision

- Real full-year forecasting remains blocked; synthetic campus track is primary.
- SLA polarity remains unresolved; source-flag experiment only.
- Opening-feature allowlist remains required (earliest rows contain outcomes).
