# IT Service Desk Intelligence

Reproducible IT operations analytics pipeline for ticket volume, bottlenecks, forecasting, and gated SLA source-flag analysis.

**Dataset:** [UCI Incident Management Process Enriched Event Log](https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log) (DOI [10.24432/C57S4H](https://doi.org/10.24432/C57S4H), CC BY 4.0).

**Audience:** nontechnical IT service managers — findings support review/planning; they do not auto-escalate tickets.

**Tableau Public:** [IT Service Desk Intelligence](https://public.tableau.com/app/profile/mohit.manoj.barade/viz/IT_Service_Desk_Intelligence/1ServiceOverview)

## Phase decisions

| Gate | Decision |
| --- | --- |
| Forecasting | **Synthetic campus track is primary** (~98% of real openings are Mar–May 2016) |
| SLA modeling | **Source-flag experiment only** — `made_sla` polarity unresolved |
| Opening features | Restricted allowlist; earliest rows contain outcome timestamps |
| Coverage | Report *observed* demand only |

## Quick start

```bash
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

docker compose up -d postgres   # host port 5433 by default
itintel migrate
itintel run --track public_historical
pytest tests/unit -q
```

Useful commands: `ingest`, `validate`, `marts`, `forecast`, `sla`, `eda`, `export`, `smoke-db`.

## Measured local results

| Item | Result |
| --- | --- |
| Raw events loaded | 141,712 (checksum-idempotent) |
| Validation | 141,712 accepted / 0 quarantined / 78 warnings |
| Tickets in marts | 24,918 over 207 opening dates |
| Quarantine proof | missing incident ID → `identity.missing_incident_number` |
| Forecast | synthetic campus; selected **seasonal_naive** |
| SLA | source-flag AP≈0.91 on test — **not** verified breach |
| CSV / Hyper release | `data/releases/LATEST_GOOD` + `dashboard/IT_Service_Desk_Intelligence.twbx` |
| Tableau Public | [live workbook](https://public.tableau.com/app/profile/mohit.manoj.barade/viz/IT_Service_Desk_Intelligence/1ServiceOverview) |

## Status

| Phase | Status |
| --- | --- |
| 0 Source verification | Done |
| 1 Foundation + Postgres | Done |
| 2 Synthetic fixtures | Done |
| 3 Raw ingestion | Done |
| 4 Validation / quarantine | Done |
| 5 Ticket marts | Done |
| 6 EDA | Done (`docs/reports/phase6_eda_*.md`) |
| 7 Forecasting | Done (synthetic) |
| 8 SLA experiment | Done as source-flag; breach claim blocked |
| 9 CSV exports | Done |
| 10 Scheduler / CI | CI workflow + crontab sketch; Supercronic image wiring optional |
| 11 Tableau Public | Done — [3-page staff workbook](https://public.tableau.com/app/profile/mohit.manoj.barade/viz/IT_Service_Desk_Intelligence/1ServiceOverview) (Show Sheets on) |
| 12 AWS deploy | **Blocked — needs AWS account access** |
| 13 Documentation | Done (guides, model cards, evidence ledger) |

## What I need from you to finish

1. **AWS** — account/profile/region + OK to create EC2/S3/IAM role/Secrets Manager (or say skip AWS for the portfolio).

Optional: author PDF confirmation of `made_sla` polarity if you want a true breach claim on the resume.

## Attribution

Amaral, C., Fantinato, M., & Peres, S. (2018). Incident management process enriched event log [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C57S4H.
