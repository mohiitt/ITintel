# Dataset Feasibility Report — Phase 0

**Generated:** 2026-11-18T23:50:48.751855+00:00  
**Source page:** https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log  
**DOI:** 10.24432/C57S4H  
**License:** Creative Commons Attribution 4.0

## Integrity

| Artifact | SHA-256 | Bytes |
| --- | --- | ---: |
| ZIP | `6294e29a311647306bfdfc85783f7df66517c197b9cd49aa5ee36ba9c525d1d6` | 2,400,214 |
| CSV | `fd184bbfd62329cfe093e99da2ea7071905f2ead91900b448eb2635870821bef` | 46,212,397 |

- Delimiter: `,`
- Timestamp format confirmed: `%d/%m/%Y %H:%M` (day/month/year hour:minute)
- Timezone: unknown; timestamps retained without invented TZ

Checksums match the planning-time inspection recorded in the implementation plan.

## Counts

| Metric | Value |
| --- | ---: |
| Event rows | 141,712 |
| Distinct incidents | 24,918 |
| Exact duplicate rows | 0 |
| Distinct opening dates | 207 |
| Events/incident (min / median / max) | 2 / 5.0 / 58 |

Reconciles with the UCI description (141,712 events / 24,918 incidents).

## Timestamp ranges

| Field | Min | Max |
| --- | --- | --- |
| opened_at (incident-level first) | 2016-02-29 01:16:00 | 2017-02-16 14:17:00 |
| sys_updated_at | 2016-02-29 01:23:00 | 2017-02-18 15:00:00 |

### Opening-month distribution (distinct incidents)

| Opening month | Distinct incidents |
| --- | ---: |
| 2016-02 | 207 |
| 2016-03 | 8,995 |
| 2016-04 | 7,934 |
| 2016-05 | 7,508 |
| 2016-06 | 5 |
| 2016-07 | 14 |
| 2016-08 | 15 |
| 2016-09 | 12 |
| 2016-10 | 16 |
| 2016-11 | 26 |
| 2016-12 | 37 |
| 2017-01 | 94 |
| 2017-02 | 55 |

**Coverage finding:** March–May 2016 account for **24,437** incidents (**98.1%** of all incidents). Later months are a severe coverage/regime warning, not routine low demand.

## Earliest-snapshot observability

| Observation | Result |
| --- | --- |
| Earliest states (top) | {'New': 16397, 'Active': 6503, 'Resolved': 1819, 'Awaiting User Info': 193, 'Awaiting Problem': 6} |
| Earliest rows with closed_at | 24,918 / 24,918 |
| Earliest rows with resolved_at | 23,362 / 24,918 |
| First-observation delay (median / min / max minutes) | 1.0 / -147.0 / 1146.0 |
| Negative first-observation delays | 5 |

**Consequence:** Enriched outcome timestamps appear on earliest rows. They must be excluded from point-in-time / opening-time feature inputs.

## made_sla investigation

| Observation | Result |
| --- | --- |
| Incidents where made_sla changes over history | 9,114 |
| Latest-observed made_sla counts | {'true': 15819, 'false': 9099} |
| Gate status | OPEN — polarity not finalized |

UCI variable prose: 'whether the incident exceeded the target SLA'. Column name 'made_sla' conventionally suggests attainment. Polarity is NOT assumed from the name; Phase 0 gate remains open until author PDF / value-transition analysis settles the semantics.

**Policy pending:** Do not train a "breach" classifier until polarity and maturity rules are documented. Prefer retaining the raw flag and an explicitly named experiment if polarity stays ambiguous.

## Physical schema note

Downloaded header uses `closed_code` (not the website prose `close_code`). Implementation must follow the CSV header.

Columns (36): `number, incident_state, active, reassignment_count, reopen_count, sys_mod_count, made_sla, caller_id, opened_by, opened_at, sys_created_by, sys_created_at, sys_updated_by, sys_updated_at, contact_type, location, category, subcategory, u_symptom, cmdb_ci, impact, urgency, priority, assignment_group, assigned_to, knowledge, u_priority_confirmation, notify, problem_id, rfc, vendor, caused_by, closed_code, resolved_by, resolved_at, closed_at`

## Gate decisions (Phase 0 exit)

| Gate | Decision |
| --- | --- |
| Real volume forecasting | FALLBACK — synthetic campus track primary |
| Weekly seasonality (real) | BLOCKED for annual/academic claims; March–May only ~13 weeks and post-May coverage collapses |
| SLA classification | CONDITIONAL — proceed only after polarity + maturity policy; sufficient latest true/false counts exist but semantics unresolved |
| Creation-time inference | RESTRICT — earliest rows often contain outcome timestamps; use explicit opening-feature allowlist / first-observed snapshot |
| Source coverage | OBSERVED demand only; March–May concentrated; do not treat missing dates after May as zero arrivals |

### Forecast track decision

**Selected primary forecast track:** synthetic campus scenarios (separately labeled).  
**Optional secondary:** March–May 2016 restricted real-data feasibility study only if completeness assumptions are stated on every export and dashboard view.

Do not train a full-year real-demand model by default. Primary forecast track: labeled synthetic campus scenarios. Optional: restricted March–May 2016 feasibility experiment with severe coverage caveats.

## Opening-feature allowlist (provisional)

Allowed only when present on an eligible opening/first-observed snapshot and not outcome-revealing:

- opened_at-derived weekday/hour (under documented TZ convention)
- impact, urgency, priority, category, subcategory, contact_type (if present at cutoff)
- verified *initial* assignment_group only

Prohibited as inputs:

- resolved_at, closed_at, closed_code, resolved_by, final incident_state
- made_sla (label / outcome)
- final assignment_group / assigned_to as if known at creation
- reopen_count / reassignment_count / sys_mod_count when only later values are available
- incident number, caller_id, analyst IDs as predictive features

## Sample daily arrivals (first / last 5 days with openings)

```
opened_date  distinct_incidents
 2016-02-29                 207
 2016-03-01                 315
 2016-03-02                 465
 2016-03-03                 392
 2016-03-04                 388
...
opened_date  distinct_incidents
 2017-02-10                   8
 2017-02-13                   5
 2017-02-14                   3
 2017-02-15                   4
 2017-02-16                   2
```

Full series: `data/profiles/daily_arrivals.csv`. Machine-readable profile: `data/profiles/source_profile.json`.

## Exit gate status

Phase 0 **passes with documented fallbacks**: no unresolved assumption is silently converted into a claimed model target. Real full-year demand forecasting and unqualified SLA-breach wording are blocked until further evidence; synthetic forecasting and descriptive analytics on the public track proceed.
