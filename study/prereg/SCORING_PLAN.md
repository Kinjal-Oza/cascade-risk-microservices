# Scoring plan for the injection study, fixed before any campaign result was looked at (2026-10-28)

The method is the paper's own code, unchanged: `graph_features.blast_radius`, `temporal_features_fast.latency_deviation_score` / `call_rate_anomaly_score` (log1p, epsilon 0.5, cumulative history, min_history 3), `cascade_score.naive_combined_score`, and `cascade_labeling.label_cascade_events` (z 3.0, min_downstream 3).

## Inputs per run, built only from the call-graph records (never from end-to-end request logs)
- **Windows:** 30-s bins from run start, 18 per run.
- **Per-service series:** for every callee (`dm`) in the run's call records, mean `rt` and call count per window. These play the roles of `mean_rt` and `mean_mcr` in the Alibaba pipeline.
- **Blast radius:** computed from um→dm call counts in the pre-fault part (0–240 s), excluding USER as caller, as in the paper.

## Methods compared (all per window; a run-level score is the maximum over services)
| ID | Method |
|---|---|
| M1 | Cascade Risk Score, naive combination (the paper's best-performing variant) |
| M2 | Latency z-score alone (the paper's single-signal baseline) |
| M3 | Static global threshold: a window alerts if any service's mean rt exceeds the global p95 of service-window mean rt in the calibration runs |
| M4 | Cascade heuristic as a detector: an event from `label_cascade_events` |
| M5 | Sliding-window latency z: same robust z, history = previous 10 windows only |
| M6 | End-to-end monitor: frontend (nginx) mean rt z-score, same formula. This is the "watch the user-facing latency" practice early warning must beat. |

## Thresholds
- **Calibration set:** the first 8 `none` runs in the campaign's randomized order. They are excluded from every reported number.
- **Threshold rule:** τ = the largest run-level window score seen in the calibration runs after min_history, so there are no alerts in calibration.
- M3 and M4 are binary, so they need no τ.

## Reported, for each method
- **Detection rate and lead time** on cascade runs. An alert counts if it falls between fault start and cascade onset + 60 s. Lead time = onset − first alert. Medians are reported, with bootstrap 95% CIs over runs.
- **False alarms per hour** over the 16 held-out `none` runs plus the pre-fault time of all fault runs.
- **Threshold-free discrimination:**
  - AUC-ROC of the run-level maximum score over the fault window, cascade versus no-cascade fault runs;
  - AUC-ROC of the per-window score, alerting windows of cascade runs versus all control windows.
- **Breakdowns** by fault type and by target (app service vs. storage).
- **Ablation** of M1's three signals: each alone, and each pair.

## Not allowed
Changing windows, thresholds, history length or the definitions in CAMPAIGN_PLAN.md after results are seen. Any later change is reported as a deviation.
