#!/usr/bin/env python3
"""Build the full 3-page staff Tableau Public workbook (Hyper extracts)."""

from __future__ import annotations

import copy
import uuid
from pathlib import Path

import pandas as pd
import pantab
from tableauhyperapi import TableName

from cwtwb.commands.common import new_editor
from cwtwb.twb_editor import TWBEditor

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "IT_Service_Desk_Intelligence.twbx"
HYPER = ROOT / "hyper"


def compat(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        d = str(out[c].dtype)
        if d.startswith("datetime") or "datetimetz" in d:
            s = pd.to_datetime(out[c], utc=True, errors="coerce")
            if getattr(s.dt, "tz", None) is not None:
                s = s.dt.tz_convert("UTC").dt.tz_localize(None)
            out[c] = s.astype("datetime64[ns]")
        elif d in {"string", "str"} or out[c].dtype == object:
            out[c] = out[c].astype(object)
        elif pd.api.types.is_bool_dtype(out[c]):
            out[c] = out[c].map({True: "yes", False: "no"}).astype(object)
    return out


def write_extract(name: str, df: pd.DataFrame) -> Path:
    HYPER.mkdir(parents=True, exist_ok=True)
    path = HYPER / f"{name}.hyper"
    if path.exists():
        path.unlink()
    pantab.frame_to_hyper(compat(df), path, table=TableName("Extract", name))
    return path


def add_hyper(editor: TWBEditor, caption: str, path: Path, table: str) -> str:
    fresh = TWBEditor("")
    fresh.set_hyper_connection(str(path.resolve()), table_name=table)
    ds = copy.deepcopy(fresh._datasource)
    new_name = "federated." + str(uuid.uuid4())
    ds.set("name", new_name)
    ds.set("caption", caption)
    editor.root.find("datasources").append(ds)
    return editor.select_datasource(new_name)


def main() -> None:
    sources = {
        "OverviewMonthly": pd.read_csv(DATA / "overview_monthly.csv"),
        "OverviewWeekday": pd.read_csv(DATA / "overview_weekday.csv"),
        "OverviewKPIs": pd.read_csv(DATA / "overview_kpis.csv"),
        "Disclosures": pd.read_csv(DATA / "disclosures.csv"),
        "Bottlenecks": pd.read_csv(DATA / "bottlenecks.csv"),
        "BottlenecksByGroup": pd.read_csv(DATA / "bottlenecks_by_group.csv"),
        "ReopenByPriority": pd.read_csv(DATA / "reopen_by_priority.csv"),
        "ForecastEval": pd.read_csv(DATA / "forecast_evaluation.csv"),
        "ForecastNext": pd.read_csv(
            DATA / "forecast_next_seven_days.csv", parse_dates=["target_date", "issue_date"]
        ),
        "TicketRisk": pd.read_csv(DATA / "ticket_risk.csv"),
        "DataQuality": pd.read_csv(DATA / "data_quality.csv"),
        "Freshness": pd.read_csv(DATA / "freshness.csv"),
    }
    paths = {n: write_extract(n, df) for n, df in sources.items()}

    editor = new_editor("")
    editor.clear_worksheets()

    first = "OverviewMonthly"
    editor.set_hyper_connection(str(paths[first].resolve()), table_name=first)
    for ds in editor.root.findall("datasources/datasource"):
        if ds.get("hasconnection") != "false":
            ds.set("caption", first)

    for name, path in paths.items():
        if name == first:
            continue
        add_hyper(editor, name, path, name)

    def chart(ds: str, ws: str, mark: str, title: str | None = None, **kw) -> None:
        editor.select_datasource(ds)
        if ws not in editor.list_worksheets():
            editor.add_worksheet(ws)
        editor.configure_chart(worksheet_name=ws, mark_type=mark, **kw)
        if title:
            editor.set_worksheet_title(ws, title)

    # ---- Page 1 worksheets ----
    chart(
        "OverviewKPIs",
        "Overview KPIs",
        "Text",
        title="Key counts (public historical)",
        rows=["metric"],
        columns=["SUM(value)"],
        label="detail",
    )
    chart(
        "OverviewMonthly",
        "Monthly Arrivals",
        "Bar",
        title="Monthly distinct openings — public historical only",
        columns=["year_month"],
        rows=["SUM(monthly_arrivals)"],
        label="SUM(days_with_openings)",
        tooltip=["coverage_note", "track_label"],
    )
    chart(
        "OverviewMonthly",
        "Month End Backlog",
        "Line",
        title="Month-end observed backlog (incomplete prehistory)",
        columns=["year_month"],
        rows=["SUM(month_end_backlog)"],
        tooltip=["track_label"],
    )
    chart(
        "OverviewWeekday",
        "Weekday Pattern",
        "Bar",
        title="Average daily openings by weekday — public historical",
        columns=["weekday_name"],
        rows=["AVG(avg_daily_arrivals)"],
        tooltip=["median_daily_arrivals", "n_days"],
    )
    chart(
        "Disclosures",
        "Overview Disclosure",
        "Text",
        title="How to read this page",
        rows=["headline"],
        columns=["ATTR(section)"],
        label="body",
    )

    # ---- Page 2 worksheets ----
    chart(
        "Bottlenecks",
        "P90 by Category",
        "Bar",
        title="p90 hours to first resolution by category (n_eligible ≥ 20)",
        columns=["AVG(p90_hours)"],
        rows=["category"],
        color="priority",
        label="SUM(n_eligible)",
        tooltip=["AVG(median_hours)", "SUM(n_missing_outcome)", "assignment_attribution"],
    )
    chart(
        "BottlenecksByGroup",
        "Volume by Assignment Group",
        "Bar",
        title="Eligible incidents by assignment group (ownership snapshot)",
        columns=["assignment_group"],
        rows=["SUM(n_eligible)"],
        tooltip=["AVG(median_of_medians_hours)", "AVG(p90_of_p90_hours)", "assignment_attribution"],
    )
    chart(
        "ReopenByPriority",
        "Reopen by Priority",
        "Bar",
        title="Observed reopen rate by opening priority",
        columns=["priority"],
        rows=["AVG(reopen_pct)"],
        label="SUM(reopened_incidents)",
        tooltip=["SUM(incidents)", "note"],
    )
    chart(
        "Disclosures",
        "Bottlenecks Disclosure",
        "Text",
        title="Bottlenecks caveats",
        rows=["headline"],
        columns=["ATTR(section)"],
        label="body",
    )

    # ---- Page 3 worksheets ----
    chart(
        "ForecastEval",
        "Forecast MAE by Model",
        "Bar",
        title="Forecast mean MAE by model — SYNTHETIC campus track",
        columns=["model"],
        rows=["AVG(mae)"],
        tooltip=["AVG(wape)", "AVG(baseline_mae)", "track_disclosure"],
    )
    chart(
        "ForecastNext",
        "Next 7 Day Forecast",
        "Bar",
        title="Next 7-day arrival forecast — SYNTHETIC (not SJSU demand)",
        columns=["target_date"],
        rows=["SUM(predicted_count)"],
        tooltip=["model_version", "track_disclosure", "issue_date"],
    )
    chart(
        "TicketRisk",
        "Source Flag Risk Queue",
        "Bar",
        title="Top source-flag scores — NOT verified SLA breach",
        columns=["incident_number"],
        rows=["AVG(score)"],
        color="above_threshold",
        tooltip=["score_label", "threshold", "model_version"],
    )
    chart(
        "DataQuality",
        "Data Quality Checks",
        "Text",
        title="Latest data-quality checks",
        rows=["rule_id"],
        columns=["SUM(failure_count)"],
        label="dq_status",
        tooltip=["rows_checked", "details", "check_status"],
    )
    chart(
        "Freshness",
        "Pipeline Freshness",
        "Text",
        title="Pipeline freshness / batch status",
        rows=["source_track"],
        columns=["SUM(row_count)"],
        label="state",
        tooltip=["accepted_count", "quarantined_count", "content_sha256"],
    )
    chart(
        "Disclosures",
        "Trust Disclosure",
        "Text",
        title="Forecast / risk / refresh disclosures",
        rows=["headline"],
        columns=["ATTR(section)"],
        label="body",
    )

    # ---- Dashboards with text banners ----
    editor.add_dashboard(
        dashboard_name="1 Service Overview",
        width=1300,
        height=1000,
        worksheet_names=[
            "Overview KPIs",
            "Monthly Arrivals",
            "Month End Backlog",
            "Weekday Pattern",
            "Overview Disclosure",
        ],
        layout={
            "type": "container",
            "direction": "vertical",
            "children": [
                {
                    "type": "text",
                    "text": "IT Service Desk Intelligence — Service Overview (public historical)",
                    "fixed_size": 48,
                    "font_size": "18",
                    "bold": True,
                },
                {
                    "type": "text",
                    "text": "Observed UCI openings only. Mar–May 2016 dominate coverage. SLA breach claim blocked.",
                    "fixed_size": 36,
                    "font_size": "11",
                },
                {"type": "worksheet", "name": "Overview KPIs", "fixed_size": 140},
                {"type": "worksheet", "name": "Monthly Arrivals", "weight": 1.2},
                {"type": "worksheet", "name": "Month End Backlog", "weight": 1.0},
                {"type": "worksheet", "name": "Weekday Pattern", "weight": 0.9},
                {"type": "worksheet", "name": "Overview Disclosure", "fixed_size": 120},
            ],
        },
    )

    editor.add_dashboard(
        dashboard_name="2 Bottlenecks",
        width=1300,
        height=1000,
        worksheet_names=[
            "P90 by Category",
            "Volume by Assignment Group",
            "Reopen by Priority",
            "Bottlenecks Disclosure",
        ],
        layout={
            "type": "container",
            "direction": "vertical",
            "children": [
                {
                    "type": "text",
                    "text": "Bottlenecks — resolution times & reopen patterns",
                    "fixed_size": 48,
                    "font_size": "18",
                    "bold": True,
                },
                {
                    "type": "text",
                    "text": "Use n_eligible denominators. Assignment group is ownership snapshot, not cause.",
                    "fixed_size": 36,
                    "font_size": "11",
                },
                {"type": "worksheet", "name": "P90 by Category", "weight": 1.3},
                {"type": "worksheet", "name": "Volume by Assignment Group", "weight": 1.0},
                {"type": "worksheet", "name": "Reopen by Priority", "weight": 0.8},
                {"type": "worksheet", "name": "Bottlenecks Disclosure", "fixed_size": 110},
            ],
        },
    )

    editor.add_dashboard(
        dashboard_name="3 Forecast Risk Trust",
        width=1300,
        height=1200,
        worksheet_names=[
            "Forecast MAE by Model",
            "Next 7 Day Forecast",
            "Source Flag Risk Queue",
            "Data Quality Checks",
            "Pipeline Freshness",
            "Trust Disclosure",
        ],
        layout={
            "type": "container",
            "direction": "vertical",
            "children": [
                {
                    "type": "text",
                    "text": "Forecast, risk & data trust",
                    "fixed_size": 48,
                    "font_size": "18",
                    "bold": True,
                },
                {
                    "type": "text",
                    "text": "Forecast = SYNTHETIC campus. Risk = source-flag only (not verified breach). Extracts refresh manually.",
                    "fixed_size": 40,
                    "font_size": "11",
                },
                {
                    "type": "container",
                    "direction": "horizontal",
                    "weight": 1.0,
                    "children": [
                        {"type": "worksheet", "name": "Forecast MAE by Model", "weight": 1},
                        {"type": "worksheet", "name": "Next 7 Day Forecast", "weight": 1},
                    ],
                },
                {"type": "worksheet", "name": "Source Flag Risk Queue", "weight": 1.1},
                {
                    "type": "container",
                    "direction": "horizontal",
                    "weight": 0.8,
                    "children": [
                        {"type": "worksheet", "name": "Data Quality Checks", "weight": 1},
                        {"type": "worksheet", "name": "Pipeline Freshness", "weight": 1},
                    ],
                },
                {"type": "worksheet", "name": "Trust Disclosure", "fixed_size": 120},
            ],
        },
    )

    for ws in editor.list_worksheets():
        editor.set_worksheet_hidden(ws, hidden=True)

    editor.set_active_dashboard("1 Service Overview")
    windows = editor.root.find("windows")
    if windows is not None:
        dash_wins = [w for w in list(windows) if w.get("class") == "dashboard"]
        other_wins = [w for w in list(windows) if w.get("class") != "dashboard"]
        for w in list(windows):
            windows.remove(w)
        for w in dash_wins + other_wins:
            windows.append(w)

    if OUT.exists():
        OUT.unlink()
    print(editor.save(OUT, validate=False))
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
