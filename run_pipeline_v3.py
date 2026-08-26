"""
Same pipeline and same algorithm as run_pipeline_v2.py, run on the FURTHER
EXPANDED real dataset (500 time-matched windows, up from 150) — 2026-08-26
checkpoint pull ("pull to ~500 windows, see where the positive count
actually lands").

Steps 1-4 are UNCHANGED in logic from run_pipeline_v2.py (same functions,
same thresholds, same real data files). The only change in this file is
memory management: at 500 windows the feature matrix has ~5x more rows
than at 150 windows, and the original Step 5 (build a Python list of
[blast_radius, latency_z, callrate_z] lists, one per (service, window)
pair, via a full services x windows nested loop) OOM-killed the process
(confirmed via dmesg: cgroup OOM at ~6.1GB RSS). This version:
  (a) frees `per_service` (the raw 12.6M-row aggregated CSV loaded into
      Python dict-of-lists) as soon as its needed pieces are extracted,
      instead of holding it alive through Step 5,
  (b) builds the feature matrix from the intersection of each service's
      actual latency_z/callrate_z window keys (skipping windows where
      no z-score exists) rather than the full services x windows cross
      product, and
  (c) accumulates into flat parallel lists (not lists-of-lists) and
      converts to compact numpy float32/int32 arrays immediately.
No formula, threshold, or algorithm changed — only how the same numbers
are computed and held in memory.
"""
import sys, gc
sys.path.insert(0, "src")

import numpy as np
import graph_features
import temporal_features_fast as temporal_features
import cascade_labeling
import cascade_score

print("=== Step 1: build call graph from real, time-matched aggregated CallGraph edges (windows 0-499) ===")
graph = graph_features.load_aggregated_edges("data/agg/callgraph_edges_matched.csv")
print(f"Callers in graph: {len(graph)}")

blast = graph_features.blast_radius(graph)
print("Top 5 blast radius:", graph_features.top_n(blast, 5))

print()
print("=== Step 2: latency deviation + call-rate anomaly from real aggregated data (500 windows) ===")
import temporal_features as orig_temporal  # only for load_aggregated
per_service = orig_temporal.load_aggregated("data/agg/msrtmcr_agg.csv")
print(f"Services in aggregated data: {len(per_service)}")

latency_z_by_service = {}
callrate_z_by_service = {}
for svc, series in per_service.items():
    lz = temporal_features.latency_deviation_score(series)
    cz = temporal_features.call_rate_anomaly_score(series)
    if lz:
        latency_z_by_service[svc] = lz
    if cz:
        callrate_z_by_service[svc] = cz

print(f"Services with a usable latency z-score (>=3 windows history): {len(latency_z_by_service)}")
print(f"Services with a usable call-rate z-score: {len(callrate_z_by_service)}")

# top-5 without redundant full recompute
all_lat = [(svc, w, z) for svc, d in latency_z_by_service.items() for w, z in d.items()]
all_lat.sort(key=lambda t: t[2], reverse=True)
print("Top 5 latency deviations:", all_lat[:5])

print()
print("=== Step 3: overlap check — services present in BOTH graph and aggregated data ===")
graph_services = set(graph.keys())
for downstream_counter in graph.values():
    graph_services.update(downstream_counter.keys())
agg_services = set(per_service.keys())
overlap = graph_services & agg_services
print(f"Graph services: {len(graph_services)}, Aggregated services: {len(agg_services)}, Overlap: {len(overlap)}")

# windows list needed downstream (used by run_evaluation.py's state dict and
# for reference) -- extract before freeing per_service.
windows = set()
for svc in per_service:
    for row in per_service[svc]:
        windows.add(row[0])
windows = sorted(windows)

# Free the raw per-service aggregated series now -- everything Step 5 needs
# (latency_z_by_service, callrate_z_by_service, blast, overlap, windows) has
# already been extracted from it. This is the single biggest memory win:
# per_service holds ~12.6M (window_idx, mean_rt, mean_mcr) tuples across
# 26,610 services.
del per_service
gc.collect()

print()
print("=== Step 4: cascade-event heuristic labeling on real data ===")
events = cascade_labeling.label_cascade_events(graph, latency_z_by_service, z_threshold=3.0, min_downstream=3)
print(f"Cascade events found (z_threshold=3.0, min_downstream=3): {len(events)}")
for e in events[:20]:
    print("  ", e)

cascade_label_keys = set()
for (um, window_idx, count, affected) in events:
    cascade_label_keys.add((um, window_idx))
    for dm in affected:
        cascade_label_keys.add((dm, window_idx))

print()
print("=== Step 5: build feature matrix (memory-efficient construction) + attempt weighted fit ===")

svc_list = []
window_list = []
br_list = []
lz_list = []
rz_list = []

for svc in sorted(overlap):
    lz_dict = latency_z_by_service.get(svc)
    if not lz_dict:
        continue
    rz_dict = callrate_z_by_service.get(svc)
    if not rz_dict:
        continue
    br = blast.get(svc, 0.0)
    # iterate the smaller dict's keys against the larger, same intersection
    # either way -- only rows where BOTH z-scores exist qualify, identical
    # filter condition to run_pipeline_v2.py's build_feature_matrix.
    if len(lz_dict) <= len(rz_dict):
        small, big = lz_dict, rz_dict
    else:
        small, big = rz_dict, lz_dict
    for w in sorted(small):
        if w in big:
            svc_list.append(svc)
            window_list.append(w)
            br_list.append(br)
            lz_list.append(lz_dict[w])
            rz_list.append(rz_dict[w])

n_rows = len(svc_list)
print(f"Feature matrix rows: {n_rows}")

br_arr = np.array(br_list, dtype=np.float64); del br_list
lz_arr = np.array(lz_list, dtype=np.float64); del lz_list
rz_arr = np.array(rz_list, dtype=np.float64); del rz_list
window_arr = np.array(window_list, dtype=np.int32); del window_list
gc.collect()

X = np.column_stack([br_arr, lz_arr, rz_arr])
del br_arr, lz_arr, rz_arr
gc.collect()

# Labels: only ~dozens of true entries (one per (svc, window) in
# cascade_label_keys) -- loop over the LABELS, not the 8-9M rows, and set
# matching positions via a vectorized boolean mask per label.
y = np.zeros(n_rows, dtype=np.int8)
svc_arr_np = np.array(svc_list, dtype=object)  # keep svc_list alive for this; see below
for (label_svc, label_w) in cascade_label_keys:
    mask = (svc_arr_np == label_svc) & (window_arr == label_w)
    y[mask] = 1

print(f"Positive labels in feature matrix: {int(y.sum())}")

model, result = cascade_score.fit_weighted_score(X, y)
if model is None:
    print("Weighted fit result:", result)
else:
    print("Weighted fit result (standardized-feature coefficients):", result)

# keys as a list of (svc, window) tuples, needed by run_evaluation.py for
# the static-SLO baseline lookup. Build it last, right before pickling, so
# it doesn't sit alongside the other intermediate structures.
keys = list(zip(svc_list, window_arr.tolist()))
del svc_list, svc_arr_np
gc.collect()

import pickle
with open("data/agg/pipeline_v3_state.pkl", "wb") as f:
    pickle.dump({
        "graph": dict(graph), "blast": blast,
        "latency_z_by_service": latency_z_by_service,
        "callrate_z_by_service": callrate_z_by_service,
        "events": events, "windows": windows, "overlap": overlap,
        "X": X, "y": y, "keys": keys, "cascade_label_keys": cascade_label_keys,
    }, f)
print("\nState saved to data/agg/pipeline_v3_state.pkl for baseline/ablation scripts.")
