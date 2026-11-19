# Tableau dashboard

**Phase 11 — 3-page staff workbook for Tableau Public**

| | |
| --- | --- |
| **Live** | [IT Service Desk Intelligence](https://public.tableau.com/app/profile/mohit.manoj.barade/viz/IT_Service_Desk_Intelligence/1ServiceOverview) |
| **Package** | [`IT_Service_Desk_Intelligence.twbx`](./IT_Service_Desk_Intelligence.twbx) |
| **Rebuild** | `python dashboard/build_tableau_workbook.py` |

Extracts are Hyper tables under `dashboard/hyper/` (regenerated on build). Source CSVs live in `dashboard/data/`.

---

## Pages

| Tab | Audience takeaway |
| --- | --- |
| **1 Service Overview** | Observed UCI openings only; Mar–May 2016 dominate; SLA breach claim blocked |
| **2 Bottlenecks** | Resolution times & reopens with `n_eligible` denominators |
| **3 Forecast Risk Trust** | Synthetic forecast + source-flag risk + DQ / freshness |

### 1 · Service Overview

- KPI strip (incidents, opening dates, reopens, SLA claim blocked)
- Monthly distinct openings (**public historical only**)
- Month-end observed backlog (not inflated daily sums)
- Weekday average openings
- Reading disclosures

### 2 · Bottlenecks

- p90 hours by category (`n_eligible` ≥ 20)
- Eligible volume by assignment group (ownership snapshot — not cause)
- Reopen % by priority
- Interpretation disclosures

### 3 · Forecast, Risk & Trust

- Forecast model MAE (**synthetic campus**)
- Next 7-day forecast (**synthetic — not SJSU demand**)
- Source-flag risk queue (**not verified breach**)
- Data quality + pipeline freshness
- Trust / refresh disclosures

---

## Show all three tabs on the web

The Mac Tableau Public app always shows local sheet tabs. **The web viewer does not**, until you enable them on the published viz.

1. Open the live viz while signed in as the owner
2. Click **gear → Settings** (upper right of the viz chrome)
3. Enable **Show Sheets**
4. Reload — tabs appear for all three dashboards

Direct view URLs (work even before Show Sheets):

| Page | Path |
| --- | --- |
| Overview | `.../viz/IT_Service_Desk_Intelligence/1ServiceOverview` |
| Bottlenecks | `.../viz/IT_Service_Desk_Intelligence/2Bottlenecks` |
| Forecast / Risk / Trust | `.../viz/IT_Service_Desk_Intelligence/3ForecastRiskTrust` |

---

## Republish from the Mac app

1. Confirm the three dashboard tabs render charts locally
2. **File → Save to Tableau Public As…** (`⇧⌘S`)
3. Overwrite workbook name: `IT_Service_Desk_Intelligence`
4. On the browser page, turn on **Show Sheets** (steps above)
