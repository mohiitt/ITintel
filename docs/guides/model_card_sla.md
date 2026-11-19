# SLA / source-flag model card

| Item | Value |
| --- | --- |
| Experiment name | Source-flag prediction (`latest_observed_made_sla`) |
| Polarity status | **Unresolved** — do not call this SLA-breach modeling |
| Features | Opening weekday/hour, impact, urgency, priority, category, contact_type, initial assignment group |
| Prohibited | resolved/closed times, close code, final state, made_sla as input, reopen/reassignment counts, IDs |
| Split | Chronological 60/20/20 by opened_at; incident-level |
| Primary ranking metric | Average precision (AP) on final test |
| Threshold | Chosen on validation for precision ≥ 0.6 when achievable; frozen for test |

## Latest local metrics (public_historical)

See artifact JSON under `data/processed/models/sla_sourceflag_*`. Example from implementation run:
- n=24,918; prevalence≈0.634
- AP(test)≈0.91
- Documented as **candidate_documented_not_breach** in `models.model_registry`

## Limitations
- UCI prose vs column name disagree on whether `made_sla=true` means exceeded or attained.
- Earliest snapshots can contain outcome timestamps; features come from allowlisted opening fields only.
- High AP with unresolved polarity is **not** a resume claim for breach detection.
