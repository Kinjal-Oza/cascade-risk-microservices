"""
Same pipeline as run_pipeline_test.py, run on the EXPANDED real dataset
(150 time-matched windows, up from 18) — 2026-08-25 extension.
Uses temporal_features_fast for the per-service scoring loop (numerically
verified equivalent to temporal_features.py on the original 18-window
data — see verification output in the session log; 778,564 values
checked, 1 float-noise-level mismatch at 1e-9). graph_features and
cascade_labeling/cascade_score are used unchanged.
"""
import sys
sys.path.insert(0, "src")

import graph_features
import temporal_features_fast as temporal_features
import cascade_labeling
import cascade_score

print("=== Step 1: build call graph from real, time-matched aggregated CallGraph edges (windows 0-149) ===")
graph = graph_features.load_aggregated_edges("data/agg/callgraph_edges_matched.csv")
print(f"Callers in graph: {len(graph)}")

blast = graph_features.blast_radius(graph)
print("Top 5 blast radius:", graph_features.top_n(blast, 5))

print()
print("=== Step 2: latency deviation + call-rate anomaly from real aggregated data (150 windows) ===")
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

print()
print("=== Step 4: cascade-event heuristic labeling on real data ===")
events = cascade_labeling.label_cascade_events(graph, latency_z_by_service, z_threshold=3.0, min_downstream=3)
print(f"Cascade events found (z_threshold=3.0, min_downstream=3): {len(events)}")
for e in events[:20]:
    print("  ", e)

print()
print("=== Step 5: build feature matrix + attempt weighted fit ===")
windows = set()
for svc in per_service:
    for row in per_service[svc]:
        windows.add(row[0])
windows = sorted(windows)

cascade_label_keys = set()
for (um, window_idx, count, affected) in events:
    cascade_label_keys.add((um, window_idx))
    for dm in affected:
        cascade_label_keys.add((dm, window_idx))

X, y, keys = cascade_score.build_feature_matrix(
    services=sorted(overlap),
    windows=windows,
    blast_radius_scores=blast,
    latency_z=latency_z_by_service,
    callrate_z=callrate_z_by_service,
    cascade_labels=cascade_label_keys,
)
print(f"Feature matrix rows: {len(X)}, positive labels: {sum(y)}")

model, result = cascade_score.fit_weighted_score(X, y)
if model is None:
    print("Weighted fit result:", result)
else:
    print("Weighted fit result (standardized-feature coefficients):", result)

import pickle
with open("data/agg/pipeline_v2_state.pkl", "wb") as f:
    pickle.dump({
        "graph": dict(graph), "blast": blast,
        "latency_z_by_service": latency_z_by_service,
        "callrate_z_by_service": callrate_z_by_service,
        "events": events, "windows": windows, "overlap": overlap,
        "X": X, "y": y, "keys": keys, "cascade_label_keys": cascade_label_keys,
    }, f)
print("\nState saved to data/agg/pipeline_v2_state.pkl for baseline/ablation scripts.")
