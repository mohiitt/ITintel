# IT Service Desk Intelligence

Reproducible IT operations analytics pipeline for ticket volume, bottlenecks, forecasting, and (gated) SLA-risk analysis. Built against the [UCI Incident Management Process Enriched Event Log](https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log) (DOI [10.24432/C57S4H](https://doi.org/10.24432/C57S4H), CC BY 4.0).

**Audience:** nontechnical IT service managers — findings support review and planning; they do not auto-escalate tickets or assign blame.

## Phase 0 decisions (verified)

| Gate | Decision |
| --- | --- |
| Forecasting | **Synthetic campus track is primary** — real openings are ~98% March–May 2016 |
| SLA modeling | **Conditional** — `made_sla` polarity unresolved; training disabled by default |
| Opening features | Restricted allowlist; earliest rows contain outcome timestamps |
| Coverage | Report *observed* demand only |

Details: [`docs/reports/phase0_feasibility_report.md`](docs/reports/phase0_feasibility_report.md), [`docs/adr/0001-forecast-and-sla-track-decisions.md`](docs/adr/0001-forecast-and-sla-track-decisions.md).

## Quick start (Phase 1)

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# PostgreSQL (Compose publishes host port 5433 by default to avoid clashing with local Postgres)
docker compose up -d postgres
# wait until healthy, then:
itintel migrate
itintel smoke-db
itintel discover

# Unit tests (no DB required)
pytest tests/unit -q
```

Optional: reproduce the source profile with `python scripts/phase0_profile_source.py` (requires the CSV under `data/raw/`).

Phase 0 artifacts: `docs/reports/phase0_feasibility_report.md`, `data/profiles/source_profile.json`.

## Repository layout

```
src/itintel/          Application (ingestion, validation, transforms, features, training, scoring, export)
sql/migrations/       Versioned schema DDL
config/               Non-secret defaults
docs/                 ADRs, contracts, reports, guides
fixtures/             Synthetic quality + campus scenario fixtures (Phase 2+)
tests/                Unit and integration tests
dashboard/            Tableau workbook assets (later)
deploy/               AWS / Compose deployment notes (later)
data/                 Local raw inputs, profiles, releases (raw CSV gitignored)
```

## Attribution

Amaral, C., Fantinato, M., & Peres, S. (2018). Incident management process enriched event log [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C57S4H.

## Status

| Phase | Status |
| --- | --- |
| 0 Feasibility / source verification | Done |
| 1 Project foundation + Compose/Postgres | Done |
| 2 Synthetic fixtures + campus scenario | Done (generators + fixtures on disk) |
| 3 Raw ingestion + batch idempotency | Done (public CSV loaded; checksum skip verified) |
| 4–13 Validation → Tableau → AWS | Not started |

CLI: `itintel migrate | smoke-db | discover | ingest [path]`.
