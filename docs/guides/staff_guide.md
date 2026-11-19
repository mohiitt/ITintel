# Staff guide (1–2 pages)

**Who this is for:** IT service managers reviewing workload and bottlenecks — not automatic ticket routing.

## What you can answer
1. How many distinct tickets opened over time (observed openings in the public historical extract)?
2. Which category/priority/group slices have longer median/p90 resolution times (with sample sizes)?
3. What does the next-7-day synthetic campus forecast say (scenario, not SJSU demand)?
4. Which tickets have higher *source-flag* risk scores (not verified SLA breach)?
5. Is the latest data release fresh, and did quality checks quarantine bad rows?

## How to read the Tableau pages (once published)
- Always check the **source track** and **data cutoff** labels.
- Prefer medians/p90 with denominators over means.
- **Unknown ≠ zero.** Missing coverage is not zero arrivals.
- Assignment group is an ownership snapshot, not proof a team caused delay.

## What this does *not* do
- Does not change staffing or escalate tickets automatically.
- Does not claim campus-wide demand from the UCI extract.
- Does not claim SLA-breach prediction until label polarity is verified.

## Refresh
Pipeline exports CSVs automatically; Tableau Public republish is **manual**. Ask the analyst which `release_*` folder / `LATEST_GOOD` pointer was used.
