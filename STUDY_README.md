# Fault-injection study and Alibaba re-analysis (added November 2026)

This folder holds the materials for the paper *Does Per-Service Anomaly Scoring Improve Early Warning? A Pre-registered Fault-Injection Study of Two Microservice Applications*.

| Path | Contents |
|---|---|
| `src/` | The Cascade Risk Score modules, unchanged from the trace analysis. This adds `graph_features`, `cascade_labeling`, `cascade_score` and `temporal_features`, which were missing from the first release. |
| `study/prereg/` | The plans, each committed before the runs it governs: `CAMPAIGN_PLAN.md`, `SCORING_PLAN.md`, `CAMPAIGN2_PLAN.md`, `ALIBABA_PLAN.md` and `GREENLIGHT_CRITERIA.md`. Deviations are appended with their timestamps. `PREREG_LOG.txt` lists every commit with its date. `prereg_history.bundle` is the full git history; inspect it with `git clone prereg_history.bundle`. |
| `study/harness/` | The testbed harness: load generator, trace collector, fault injector and campaign drivers for both studies. It includes the GitHub Actions workflows that ran them, and `dsb.patch`, the two-line change to DeathStarBench commit 6ecb097. |
| `study/analysis/` | The scoring code (`score_testbed.py` for Study 1, `score2.py` for Study 2), the exploratory analyses (`reanalysis.py`, `tier_summary.py`, `missingness.py`, `noncascade_study1.py`, `explore_*.py`), `figures.py` / `figures_v3.py`, and `tests/`, the scorer's invariant tests. |
| `study/results/` | Scored results, the verdicts, and the Alibaba reproduction and forward-evaluation outputs. |
| `alibaba/reanalysis_kernel.py` | The Kaggle kernel that re-pulls 500 trace windows, reproduces the original analysis and runs the forward evaluation. `operating_points.py` adds precision at fixed alert fractions and the row-to-event mapping (exploratory). |
| `study/results/PROVENANCE.md` | Chronology with external (Kaggle) timestamps, and container image digests. |

## Reproducing
1. **Run the studies.** Push `study/harness` to a GitHub repository with the secret `KAGGLE_API_TOKEN`. The workflows start DeathStarBench, run the campaign shards, and upload each shard's run data.
2. **Score.** Run `python3 study/analysis/score_testbed.py <runs> out.json` for Study 1, and `python3 study/analysis/score2.py <runs> out.json` for Study 2.
3. **Exploratory re-analysis.** `python3 study/analysis/reanalysis.py 2 <study-2 runs> out.json` (and `1` for Study 1). Run the tests with `python3 -m pytest study/analysis/tests`; set `CRS_RUNDIR` to also rescore the raw Study 2 data against the published numbers.
4. **Alibaba re-analysis.** Run `alibaba/reanalysis_kernel.py` on Kaggle (CPU, internet on), with `src/` and the `trace_pipeline` scripts attached as a dataset.

## Raw run data
Each run's request log, call-graph records and (in Study 2) cgroup samples come to about 850 MB in total. They are published as Kaggle datasets, `kinjalvaishnav/crs-campaign-*` and `kinjalvaishnav/crs-c2-*`.
