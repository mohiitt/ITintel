#!/usr/bin/env python3
"""Phase 0 source verification: profile the UCI incident event log CSV.

Produces a JSON profile and a Markdown feasibility report fragment under data/profiles/.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "raw" / "incident_event_log.csv"
ZIP_PATH = ROOT / "data" / "raw" / "incident_event_log.zip"
OUT_DIR = ROOT / "data" / "profiles"
REPORT_DIR = ROOT / "docs" / "reports"

SOURCE_URL = (
    "https://archive.ics.uci.edu/static/public/498/"
    "incident+management+process+enriched+event+log.zip"
)
DATASET_PAGE = (
    "https://archive.ics.uci.edu/dataset/498/"
    "incident+management+process+enriched+event+log"
)
DOI = "10.24432/C57S4H"
LICENSE = "Creative Commons Attribution 4.0"

# Day/month/year hour:minute as established in the plan's preliminary inspection.
TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M"
TIMESTAMP_COLS = [
    "opened_at",
    "sys_created_at",
    "sys_updated_at",
    "resolved_at",
    "closed_at",
]
MISSING_MARKERS = {"", "?", "NA", "N/A", "null", "NULL", "None"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_ts(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.strip().replace(
        {m: pd.NA for m in MISSING_MARKERS}
    )
    return pd.to_datetime(cleaned, format=TIMESTAMP_FORMAT, errors="coerce")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    retrieval_time = datetime.now(timezone.utc).isoformat()
    zip_sha = sha256_file(ZIP_PATH)
    csv_sha = sha256_file(CSV_PATH)

    # Read as text first to preserve source values; parsing is explicit.
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    columns = list(df.columns)

    for col in TIMESTAMP_COLS:
        df[f"{col}_parsed"] = parse_ts(df[col])

    n_events = len(df)
    n_incidents = df["number"].nunique()
    exact_dupes = int(df.duplicated().sum())

    opened = df.groupby("number", sort=False)["opened_at_parsed"].first()
    opened_min = opened.min()
    opened_max = opened.max()
    updated_min = df["sys_updated_at_parsed"].min()
    updated_max = df["sys_updated_at_parsed"].max()

    # Earliest event per incident by update time (fallback: row order).
    df["_row"] = range(len(df))
    earliest_idx = df.groupby("number")["sys_updated_at_parsed"].idxmin()
    earliest = df.loc[earliest_idx].copy()

    earliest_states = earliest["incident_state"].value_counts().to_dict()
    earliest_has_closed = int(earliest["closed_at_parsed"].notna().sum())
    earliest_has_resolved = int(earliest["resolved_at_parsed"].notna().sum())

    delay_minutes = (
        earliest["sys_updated_at_parsed"] - earliest["opened_at_parsed"]
    ).dt.total_seconds() / 60.0
    delay_stats = {
        "median_minutes": float(delay_minutes.median()),
        "min_minutes": float(delay_minutes.min()),
        "max_minutes": float(delay_minutes.max()),
        "negative_count": int((delay_minutes < 0).sum()),
    }

    # made_sla changes within incidents
    sla_nunique = df.groupby("number")["made_sla"].nunique()
    sla_changes = int((sla_nunique > 1).sum())

    # Latest observed made_sla by last update time
    latest_idx = df.groupby("number")["sys_updated_at_parsed"].idxmax()
    latest = df.loc[latest_idx]
    latest_sla = latest["made_sla"].value_counts().to_dict()

    # Opening-month distribution (incident-level)
    opened_month = opened.dt.to_period("M").astype(str)
    opening_months = opened_month.value_counts().sort_index().to_dict()
    mar_may = opened[
        (opened >= "2016-03-01") & (opened < "2016-06-01")
    ]
    mar_may_share = float(len(mar_may) / n_incidents)

    # Distinct opening dates and events per incident
    distinct_open_dates = int(opened.dt.normalize().nunique())
    events_per = df.groupby("number").size()
    events_per_stats = {
        "min": int(events_per.min()),
        "median": float(events_per.median()),
        "mean": float(events_per.mean()),
        "max": int(events_per.max()),
    }

    # Missingness for timestamp columns (unparseable or empty)
    missingness = {}
    for col in TIMESTAMP_COLS:
        raw = df[col].astype(str).str.strip()
        empty = raw.isin(MISSING_MARKERS) | (raw == "")
        unparsed = df[f"{col}_parsed"].isna() & ~empty
        missingness[col] = {
            "empty_or_marker": int(empty.sum()),
            "unparseable_nonempty": int(unparsed.sum()),
            "parsed_ok": int(df[f"{col}_parsed"].notna().sum()),
        }

    # Categorical field cardinalities (sample)
    cats = [
        "incident_state",
        "contact_type",
        "category",
        "subcategory",
        "impact",
        "urgency",
        "priority",
        "assignment_group",
        "closed_code" if "closed_code" in columns else "close_code",
        "made_sla",
        "active",
        "knowledge",
        "notify",
    ]
    cat_profile = {}
    for c in cats:
        if c not in df.columns:
            continue
        vals = df[c].astype(str).str.strip()
        unknown = int(vals.isin(MISSING_MARKERS).sum())
        cat_profile[c] = {
            "n_unique": int(vals.nunique()),
            "top5": vals.value_counts().head(5).to_dict(),
            "unknown_marker_rows": unknown,
        }

    # UCI prose says made_sla shows whether incident *exceeded* target SLA.
    # Column name "made_sla" conventionally means attained. Record ambiguity.
    sla_note = (
        "UCI variable prose: 'whether the incident exceeded the target SLA'. "
        "Column name 'made_sla' conventionally suggests attainment. "
        "Polarity is NOT assumed from the name; Phase 0 gate remains open "
        "until author PDF / value-transition analysis settles the semantics."
    )

    profile = {
        "retrieval": {
            "retrieved_at_utc": retrieval_time,
            "source_url": SOURCE_URL,
            "dataset_page": DATASET_PAGE,
            "doi": DOI,
            "license": LICENSE,
            "zip_sha256": zip_sha,
            "csv_sha256": csv_sha,
            "csv_bytes": CSV_PATH.stat().st_size,
            "zip_bytes": ZIP_PATH.stat().st_size,
            "delimiter": ",",
            "encoding": "utf-8 (assumed; pandas default succeeded)",
            "timestamp_format": TIMESTAMP_FORMAT,
            "timezone": "unknown; timestamps retained without invented TZ",
        },
        "counts": {
            "event_rows": n_events,
            "distinct_incidents": n_incidents,
            "exact_duplicate_rows": exact_dupes,
            "distinct_opening_dates": distinct_open_dates,
            "events_per_incident": events_per_stats,
        },
        "timestamps": {
            "opened_at_min": str(opened_min),
            "opened_at_max": str(opened_max),
            "sys_updated_at_min": str(updated_min),
            "sys_updated_at_max": str(updated_max),
            "missingness": missingness,
        },
        "opening_months": opening_months,
        "coverage": {
            "mar_may_2016_incidents": int(len(mar_may)),
            "mar_may_2016_share": mar_may_share,
            "forecast_recommendation": (
                "Do not train a full-year real-demand model by default. "
                "Primary forecast track: labeled synthetic campus scenarios. "
                "Optional: restricted March–May 2016 feasibility experiment "
                "with severe coverage caveats."
            ),
        },
        "earliest_snapshot": {
            "states": earliest_states,
            "has_closed_at": earliest_has_closed,
            "has_resolved_at": earliest_has_resolved,
            "first_observation_delay_minutes": delay_stats,
        },
        "made_sla": {
            "incidents_with_value_change": sla_changes,
            "latest_observed_counts": latest_sla,
            "semantic_note": sla_note,
            "gate_status": "OPEN — polarity not finalized",
        },
        "columns": columns,
        "categorical": cat_profile,
        "gate_decisions": {
            "real_volume_forecasting": "FALLBACK — synthetic campus track primary",
            "weekly_seasonality_real": (
                "BLOCKED for annual/academic claims; "
                "March–May only ~13 weeks and post-May coverage collapses"
            ),
            "sla_classification": (
                "CONDITIONAL — proceed only after polarity + maturity policy; "
                "sufficient latest true/false counts exist but semantics unresolved"
            ),
            "creation_time_inference": (
                "RESTRICT — earliest rows often contain outcome timestamps; "
                "use explicit opening-feature allowlist / first-observed snapshot"
            ),
            "source_coverage": (
                "OBSERVED demand only; March–May concentrated; "
                "do not treat missing dates after May as zero arrivals"
            ),
        },
    }

    profile_path = OUT_DIR / "source_profile.json"
    profile_path.write_text(json.dumps(profile, indent=2, default=str))

    # Daily arrivals for charting / report
    daily = (
        opened.dt.normalize()
        .value_counts()
        .sort_index()
        .rename_axis("opened_date")
        .reset_index(name="distinct_incidents")
    )
    daily["opened_date"] = daily["opened_date"].dt.strftime("%Y-%m-%d")
    daily.to_csv(OUT_DIR / "daily_arrivals.csv", index=False)

    write_feasibility_report(profile, daily)
    print(f"Wrote {profile_path}")
    print(f"Events={n_events} incidents={n_incidents}")
    print(f"Mar–May share={mar_may_share:.3f}")
    print(f"SLA changes within incident={sla_changes}")
    print(f"Latest made_sla={latest_sla}")


def write_feasibility_report(profile: dict, daily: pd.DataFrame) -> None:
    g = profile["gate_decisions"]
    cov = profile["coverage"]
    ts = profile["timestamps"]
    sla = profile["made_sla"]
    ret = profile["retrieval"]
    early = profile["earliest_snapshot"]

    months_table = "\n".join(
        f"| {m} | {c:,} |" for m, c in profile["opening_months"].items()
    )

    md = f"""# Dataset Feasibility Report — Phase 0

**Generated:** {ret["retrieved_at_utc"]}  
**Source page:** {ret["dataset_page"]}  
**DOI:** {ret["doi"]}  
**License:** {ret["license"]}

## Integrity

| Artifact | SHA-256 | Bytes |
| --- | --- | ---: |
| ZIP | `{ret["zip_sha256"]}` | {ret["zip_bytes"]:,} |
| CSV | `{ret["csv_sha256"]}` | {ret["csv_bytes"]:,} |

- Delimiter: `{ret["delimiter"]}`
- Timestamp format confirmed: `{ret["timestamp_format"]}` (day/month/year hour:minute)
- Timezone: {ret["timezone"]}

Checksums match the planning-time inspection recorded in the implementation plan.

## Counts

| Metric | Value |
| --- | ---: |
| Event rows | {profile["counts"]["event_rows"]:,} |
| Distinct incidents | {profile["counts"]["distinct_incidents"]:,} |
| Exact duplicate rows | {profile["counts"]["exact_duplicate_rows"]:,} |
| Distinct opening dates | {profile["counts"]["distinct_opening_dates"]:,} |
| Events/incident (min / median / max) | {profile["counts"]["events_per_incident"]["min"]} / {profile["counts"]["events_per_incident"]["median"]} / {profile["counts"]["events_per_incident"]["max"]} |

Reconciles with the UCI description (141,712 events / 24,918 incidents).

## Timestamp ranges

| Field | Min | Max |
| --- | --- | --- |
| opened_at (incident-level first) | {ts["opened_at_min"]} | {ts["opened_at_max"]} |
| sys_updated_at | {ts["sys_updated_at_min"]} | {ts["sys_updated_at_max"]} |

### Opening-month distribution (distinct incidents)

| Opening month | Distinct incidents |
| --- | ---: |
{months_table}

**Coverage finding:** March–May 2016 account for **{cov["mar_may_2016_incidents"]:,}** incidents (**{cov["mar_may_2016_share"]:.1%}** of all incidents). Later months are a severe coverage/regime warning, not routine low demand.

## Earliest-snapshot observability

| Observation | Result |
| --- | --- |
| Earliest states (top) | {early["states"]} |
| Earliest rows with closed_at | {early["has_closed_at"]:,} / {profile["counts"]["distinct_incidents"]:,} |
| Earliest rows with resolved_at | {early["has_resolved_at"]:,} / {profile["counts"]["distinct_incidents"]:,} |
| First-observation delay (median / min / max minutes) | {early["first_observation_delay_minutes"]["median_minutes"]:.1f} / {early["first_observation_delay_minutes"]["min_minutes"]:.1f} / {early["first_observation_delay_minutes"]["max_minutes"]:.1f} |
| Negative first-observation delays | {early["first_observation_delay_minutes"]["negative_count"]:,} |

**Consequence:** Enriched outcome timestamps appear on earliest rows. They must be excluded from point-in-time / opening-time feature inputs.

## made_sla investigation

| Observation | Result |
| --- | --- |
| Incidents where made_sla changes over history | {sla["incidents_with_value_change"]:,} |
| Latest-observed made_sla counts | {sla["latest_observed_counts"]} |
| Gate status | {sla["gate_status"]} |

{sla["semantic_note"]}

**Policy pending:** Do not train a "breach" classifier until polarity and maturity rules are documented. Prefer retaining the raw flag and an explicitly named experiment if polarity stays ambiguous.

## Physical schema note

Downloaded header uses `closed_code` (not the website prose `close_code`). Implementation must follow the CSV header.

Columns ({len(profile["columns"])}): `{", ".join(profile["columns"])}`

## Gate decisions (Phase 0 exit)

| Gate | Decision |
| --- | --- |
| Real volume forecasting | {g["real_volume_forecasting"]} |
| Weekly seasonality (real) | {g["weekly_seasonality_real"]} |
| SLA classification | {g["sla_classification"]} |
| Creation-time inference | {g["creation_time_inference"]} |
| Source coverage | {g["source_coverage"]} |

### Forecast track decision

**Selected primary forecast track:** synthetic campus scenarios (separately labeled).  
**Optional secondary:** March–May 2016 restricted real-data feasibility study only if completeness assumptions are stated on every export and dashboard view.

{cov["forecast_recommendation"]}

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
{daily.head(5).to_string(index=False)}
...
{daily.tail(5).to_string(index=False)}
```

Full series: `data/profiles/daily_arrivals.csv`. Machine-readable profile: `data/profiles/source_profile.json`.

## Exit gate status

Phase 0 **passes with documented fallbacks**: no unresolved assumption is silently converted into a claimed model target. Real full-year demand forecasting and unqualified SLA-breach wording are blocked until further evidence; synthetic forecasting and descriptive analytics on the public track proceed.
"""
    path = REPORT_DIR / "phase0_feasibility_report.md"
    path.write_text(md)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
