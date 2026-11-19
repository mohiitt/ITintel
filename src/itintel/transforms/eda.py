"""Phase 6 exploratory analysis report and charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from itintel.config import ROOT, AppConfig, load_config
from itintel.db.connection import connect

REPORT_DIR = ROOT / "docs" / "reports"
CHART_DIR = ROOT / "docs" / "reports" / "charts"


def write_eda_report(source_track: str = "public_historical", *, config: AppConfig | None = None) -> Path:
    cfg = config or load_config()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    with connect(cfg.database) as conn:
        tickets = _df(
            conn,
            """
            SELECT * FROM marts.fact_tickets WHERE source_track = %s
            """,
            (source_track,),
        )
        daily = _df(
            conn,
            """
            SELECT * FROM marts.daily_volume WHERE source_track = %s ORDER BY arrival_date
            """,
            (source_track,),
        )
        res = _df(
            conn,
            """
            SELECT * FROM marts.resolution_stats WHERE source_track = %s
            """,
            (source_track,),
        )
        dq = _df(
            conn,
            """
            SELECT status, rows_checked, rows_accepted, rows_quarantined
            FROM ops.dq_runs
            ORDER BY started_at DESC LIMIT 5
            """,
        )

    # Charts
    if not daily.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(pd.to_datetime(daily["arrival_date"]), daily["distinct_arrivals"], lw=1.2)
        ax.set_title(f"Distinct ticket arrivals — {source_track}")
        ax.set_xlabel("Opening date")
        ax.set_ylabel("Distinct incidents")
        fig.tight_layout()
        fig.savefig(CHART_DIR / f"arrivals_{source_track}.png", dpi=120)
        plt.close(fig)

    if not tickets.empty and tickets["first_resolved_at"].notna().any():
        dur = (
            pd.to_datetime(tickets["first_resolved_at"]) - pd.to_datetime(tickets["opened_at"])
        ).dt.total_seconds() / 3600.0
        dur = dur[(dur >= 0) & dur.notna()]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(dur.clip(upper=dur.quantile(0.95)), bins=40, color="#3d5a80")
        ax.set_title(f"Time to first resolution (hours, clipped p95) — {source_track}")
        ax.set_xlabel("Hours")
        fig.tight_layout()
        fig.savefig(CHART_DIR / f"resolution_hours_{source_track}.png", dpi=120)
        plt.close(fig)

    n = len(tickets)
    reopen_rate = float(tickets["reopen_observed"].mean()) if n else None
    sla_counts = (
        tickets["latest_made_sla"].value_counts(dropna=False).to_dict() if n else {}
    )
    top_cat = (
        tickets["opening_category"].fillna("UNKNOWN").value_counts().head(10).to_dict()
        if n
        else {}
    )

    # Three candidate findings
    findings = []
    if not daily.empty:
        peak = daily.loc[daily["distinct_arrivals"].idxmax()]
        findings.append(
            {
                "observation": "Arrival volume is highly concentrated in a short calendar window.",
                "measure": (
                    f"Peak day {peak['arrival_date']} had {peak['distinct_arrivals']} openings; "
                    f"{len(daily)} distinct opening dates overall."
                ),
                "alternative": "Source export coverage may truncate later months rather than demand falling.",
                "follow_up": "Keep synthetic forecast track separate; label observed vs total demand.",
            }
        )
    if reopen_rate is not None:
        findings.append(
            {
                "observation": "A non-trivial share of incidents show an observed reopen signal.",
                "measure": f"reopen_observed rate = {reopen_rate:.1%} of {n:,} incidents.",
                "alternative": "reopen_count may be backfilled; not proof of agent error.",
                "follow_up": "Use state-history intervals for backlog; avoid causal staffing claims.",
            }
        )
    if res is not None and not res.empty:
        slow = res.sort_values("p90_hours", ascending=False).head(1)
        row = slow.iloc[0]
        findings.append(
            {
                "observation": "Some category/priority/group slices have much longer p90 resolution times.",
                "measure": (
                    f"Highest p90 in export: category={row['category']}, priority={row['priority']}, "
                    f"group={row['assignment_group']}, p90_hours={row['p90_hours']}, "
                    f"n_eligible={row['n_eligible']}."
                ),
                "alternative": "Assignment group is ownership snapshot, not proven cause of delay.",
                "follow_up": "Investigate with denominators visible; do not average category medians.",
            }
        )

    md = f"""# Phase 6 — Exploratory analysis ({source_track})

## Coverage

| Metric | Value |
| --- | ---: |
| Distinct incidents | {n:,} |
| Distinct opening dates | {len(daily):,} |
| Reopen observed rate | {reopen_rate if reopen_rate is not None else 'n/a'} |
| Latest made_sla counts | {sla_counts} |

DQ recent runs: {dq.to_dict(orient='records') if not dq.empty else 'none'}

Charts: `docs/reports/charts/arrivals_{source_track}.png`, `docs/reports/charts/resolution_hours_{source_track}.png`.

## Top opening categories

| Category | Incidents |
| --- | ---: |
{chr(10).join(f'| {k} | {v} |' for k, v in top_cat.items()) if top_cat else '| _(none)_ | 0 |'}

## Candidate findings

"""
    for i, fnd in enumerate(findings, 1):
        md += f"""### Finding {i}
- **Observation:** {fnd['observation']}
- **Measure:** {fnd['measure']}
- **Alternative explanation:** {fnd['alternative']}
- **Follow-up:** {fnd['follow_up']}

"""
    md += """
## Model feasibility revision

- Real full-year forecasting remains blocked; synthetic campus track is primary.
- SLA polarity remains unresolved; source-flag experiment only.
- Opening-feature allowlist remains required (earliest rows contain outcomes).
"""
    path = REPORT_DIR / f"phase6_eda_{source_track}.md"
    path.write_text(md)
    return path


def _df(conn, sql: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        cols = [d.name for d in cur.description] if cur.description else []
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)
