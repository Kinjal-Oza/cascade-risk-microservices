# cascade-risk-microservices

Reproducibility harness for a TNSM paper on cascading latency failure
detection in microservice dependency chains. All results trace back to
code run on real, publicly downloaded production trace data (Alibaba
`cluster-trace-microservices-v2022`) — nothing here is synthetic or
fabricated.

## Status (2026-08-26)

Full pipeline run complete on 500 real, time-matched windows (up from
150 on 2026-08-25, up from 18 on 2026-08-18) — 27.8x more data than
the original validation pass. This is the checkpoint Kinjal asked for
("pull to ~500 windows, see where the positive count actually lands,
decide from there") — decision made: stop pulling data, finish the
write-up, submit.

- `src/graph_features.py` — blast-radius scoring. Real, tested.
- `src/temporal_features.py` — original O(n^2) latency/call-rate z-score module (correct, used for the 18-window validation).
- `src/temporal_features_fast.py` — O(n) reimplementation, numerically verified equivalent to the original (778,564 values checked, 1 float-noise-level mismatch at 1e-9) before use at scale.
- `src/cascade_labeling.py` — heuristic cascade-event labeling.
- `src/cascade_score.py` — logistic-regression fit + naive combined score.
- `src/baselines.py` — static SLO threshold + rolling-z-score-only baselines.
- `run_pipeline_v3.py` — full pipeline on the 500-window data. New 2026-08-26. (`run_pipeline_v2.py` is kept for the 150-window checkpoint; superseded, not deleted, so the intermediate result stays reproducible.)
- `run_evaluation_v3b.py` — AUC-ROC evaluation + ablations + lead-time check on the 500-window data. New 2026-08-26. (Two intermediate versions, `run_evaluation_v3.py` and the dict-based first attempt, hit a real container OOM at this data volume — see "Memory note" below. `run_evaluation.py` is kept for the 150-window checkpoint.)

**Raw aggregated data files (`data/agg/msrtmcr_agg.csv` ~477MB, `data/agg/callgraph_edges_matched.csv` ~6MB, `data/agg/cg_windows/` ~457MB) are NOT included in this folder.** They were too large to transfer out of the cloud session that built them (device-bridge cap). They exist only in that session's ephemeral workspace as of 2026-08-26 — re-running the pull (see "Reproducing the 500-window pull" below) regenerates them from the same public source.

## Key real finding (2026-08-26)

The 150-window checkpoint (2026-08-25) found that an 8.3x data increase barely moved the positive-label count (8 events -> 9 rows) — genuinely rare cascades, or so it looked at the time. Pulling further to 500 windows (3.33x more on top of that) told a different story: 8 cascade events (up from 2), 31 positive-labeled rows (up from 9). Growth was not proportional to data volume in either direction — it was bursty. Six of the eight events cluster inside a single 45-window (~2.25 hour) span (indices 173-218); the other two sit at windows 5-6. Real production systems have incidents concentrated in time; a longer, uniform-looking pull can still hide (or reveal) that unevenly.

Headline evaluation numbers (AUC-ROC, 500-window data):
- Cascade Risk Score (all 3 signals, fitted): 0.8267
- Naive unweighted combination (unfitted): 0.8360 — **beats the fitted model.** Not hidden; explained in the paper's Section 7.
- Latency z-score alone (baseline): 0.7944 — now clearly separated from the combined scores (was statistically indistinguishable at 150 windows)
- Static global SLO threshold (baseline): 0.5558
- Ablations: blast_radius alone 0.6706 (was 0.5489 at 150 windows — real signal now), callrate_z alone 0.4740 (below chance — flagged honestly, not hidden)

## Memory note (2026-08-26)

At 500 windows the feature matrix is ~8.5M rows. The original list-of-lists
`build_feature_matrix` + a full `{(service,window): score}` dict for the
static-SLO baseline both OOM-killed the container (confirmed via dmesg,
cgroup limit ~6.1GB). Fixed by: freeing the raw per-service dict as soon
as its needed pieces are extracted, building the feature matrix from flat
numpy arrays instead of Python object lists, and computing the static-SLO
baseline via a pandas columnar merge instead of a per-row dict lookup. No
formula or threshold changed — same numbers, cheaper to compute.

## Not yet done

- Push to GitHub under Kinjal-Oza (personal identity, MIT license, per project safety rules) — needs to happen from Kinjal's own machine/credentials, and needs the raw data regenerated first (see above).
- MicroNet full-text comparison — still paywalled at IEEE Xplore and ACM DL as of 2026-08-26.
- Resolve Alibaba license confirmation (email sent 2026-08-25, awaiting reply — no response yet; fallback already written into the paper's Section 3).
- Kinjal's final read-through and sign-off before submission.

## Related work — done this session (2026-08-26)

Four new citations added, each fetched and verified against its real
source (not generated from a title guess): Zhang et al. 2024 (failure
diagnosis survey), Soldani et al. 2025 (log-based cascade explanation),
Fang et al. 2025 (RCA benchmark evaluation rigor), Li 2026 (GNN-based
propagation prediction, proprietary data — cited for contrast).

## Dataset

`github.com/alibaba/clusterdata`, `cluster-trace-microservices-v2022`.
License confirmation requested from the trace maintainers 2026-08-25,
awaiting reply. README states research/study-purpose use is permitted.

**License note for this repo.** This repo contains no raw or aggregated Alibaba trace data — only original pipeline code, evaluation code, and summary log output (aggregate statistics, AUC numbers). Nothing here redistributes the dataset itself. The trace program's own public README (as of 2026-08-25) states the data may be used "for research or study purpose"; written confirmation that this covers publishing derived results was separately requested from the maintainers on 2026-08-25 and is still pending as of this repo's last update. That open question applies to the paper's use of the data, not to this code repo.

## Reproducing the 500-window pull

The raw data isn't in this folder (see above), but the pull is fully
scripted and reproducible from the public source:

```
# MSRTMCR and CallGraph streams, windows 0-499, from
# https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2022MicroservicesTraces/
# (same streaming curl | tar -xzO | awk pattern used throughout this project)
python3 run_pipeline_v3.py       # full pipeline, 500-window data
python3 run_evaluation_v3b.py    # AUC-ROC evaluation + ablations
```
