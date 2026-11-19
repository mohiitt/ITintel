# Evidence ledger

| Claim | Value / pointer | Snapshot |
| --- | --- | --- |
| Source ZIP SHA-256 | `6294e29a311647306bfdfc85783f7df66517c197b9cd49aa5ee36ba9c525d1d6` | Phase 0 profile |
| Source CSV SHA-256 | `fd184bbfd62329cfe093e99da2ea7071905f2ead91900b448eb2635870821bef` | Phase 0 / raw batch |
| Events / incidents | 141,712 / 24,918 | raw + marts |
| Validation | 141,712 accepted, 0 quarantined, 78 warnings | dq_run `120e86eb-…` |
| Quarantine proof | missing incident ID → `identity.missing_incident_number` | synthetic_quality batch |
| Marts | 24,918 tickets; 207 opening dates | `itintel marts` |
| Forecast track | synthetic_campus; selected seasonal_naive | model_registry |
| SLA experiment | source-flag only; polarity unresolved | model card |
| Export release | `data/releases/LATEST_GOOD` → release folder with 7 CSVs + manifest | Phase 9 |
| Tableau Public | https://public.tableau.com/app/profile/mohit.manoj.barade/viz/IT_Service_Desk_Intelligence/1ServiceOverview | Phase 11 done — 3 staff dashboards; Show Sheets enabled |
| Tableau package | `dashboard/IT_Service_Desk_Intelligence.twbx` (Hyper extracts) | Phase 11 |

Update this table whenever public claims change.
