# Forecast model card

| Item | Value |
| --- | --- |
| Target | Next 7 daily arrival counts |
| Primary track | `synthetic_campus` (illustrative calendar; not SJSU demand) |
| Horizon | 7 days (fixed before evaluation) |
| Baselines | Seasonal naive (same weekday last week); 14-day moving average |
| Challenger | Weekly seasonal ETS (Holt-Winters) |
| Selection | Lowest mean MAE across expanding-window folds |
| Split | Expanding origin, disjoint 7-day evaluation windows after 28-day warm-up |
| Metrics | MAE (tickets/day), WAPE when denominator > 0, improvement vs seasonal naive |

## Selected result (latest local run)

Selected model: **seasonal_naive** (challengers did not beat the baseline on mean MAE in this run — baseline remains deployable).

Predictions stored in `models.forecast_predictions` and exported as `forecast_next_seven_days.csv`.

## Limitations
- Synthetic generator assumptions (weekday pattern, registration/term/finals bursts, noise).
- Not evidence of real campus demand or annual seasonality learning.
- Real UCI openings fail the full-year coverage gate (~98% March–May 2016).
