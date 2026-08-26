"""
Same as run_evaluation_v3.py -- identical AUC-ROC methodology, identical
baselines, identical ablation combos -- but with the static-SLO baseline
lookup rewritten using pandas columnar operations instead of a Python
dict-of-dicts, after the dict-based version OOM-killed the process (the
combination of X/y/keys already in memory (~1.5GB) plus a second
~12.6M-row Python dict copy of the raw aggregated data pushed past the
container's 6GB cgroup limit -- confirmed via dmesg).

The threshold computation and the definition of the static-SLO score
(1.0 if a service's mean_rt in that window exceeds the GLOBAL p95 of
mean_rt across the whole dataset, else 0.0) are UNCHANGED -- same
formula as baselines.static_slo_threshold_score, just computed via a
merge instead of a per-row dict lookup, which is the only thing being
changed here for memory reasons.
"""
import sys, pickle, gc
sys.path.insert(0, "src")
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import cascade_score

with open("data/agg/pipeline_v3_state.pkl", "rb") as f:
    state = pickle.load(f)

X = np.array(state["X"])
y = np.array(state["y"])
keys = state["keys"]
print(f"Evaluation set: {len(y)} rows, {int(y.sum())} positives, {len(y)-int(y.sum())} negatives")
print()

def auc(scores, label=""):
    try:
        val = roc_auc_score(y, scores)
        print(f"{label}: AUC-ROC = {val:.4f}")
        return val
    except Exception as e:
        print(f"{label}: could not compute ({e})")
        return None

results = {}

print("=== Full Cascade Risk Score (all 3 signals, fitted logistic regression) ===")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
model_full = LogisticRegression()
model_full.fit(X_scaled, y)
scores_full = model_full.predict_proba(X_scaled)[:, 1]
results["cascade_risk_score_full"] = auc(scores_full, "Cascade Risk Score (blast+latency+callrate, fitted)")

print()
print("=== Naive unsupervised combined score (unweighted sigmoid, no fitting) ===")
naive_scores = np.array([cascade_score.naive_combined_score(*row) for row in X])
results["naive_combined"] = auc(naive_scores, "Naive combined score (unfitted sanity baseline)")

print()
print("=== Baseline 1: rolling z-score only (latency signal alone, no graph/call-rate) ===")
results["latency_z_only"] = auc(X[:, 1], "Latency z-score alone")

print()
print("=== Baseline 2: static global SLO threshold (binary, single global cutoff) ===")
# Columnar load: category dtype for msname (26,610 uniques -> small int codes
# under the hood), int32 for window_idx, float32 for mean_rt. This is the
# same raw file (data/agg/msrtmcr_agg.csv, all 500 windows) but held as
# flat typed arrays instead of a Python dict-of-dicts.
agg_df = pd.read_csv(
    "data/agg/msrtmcr_agg.csv",
    usecols=["window_idx", "msname", "mean_rt"],
    dtype={"window_idx": "int32", "msname": "category", "mean_rt": "float32"},
)
print(f"Loaded {len(agg_df)} raw aggregated rows for static-SLO baseline.")

# EXACT same threshold definition as baselines.static_slo_threshold_score:
# sort all mean_rt values ascending, take the value at index int(n * 0.95).
rt_sorted = np.sort(agg_df["mean_rt"].to_numpy())
idx = int(len(rt_sorted) * 0.95)
static_threshold = float(rt_sorted[min(idx, len(rt_sorted) - 1)])
del rt_sorted
print(f"(Global p95 latency threshold used: {static_threshold:.2f}ms)")

# Keys -> DataFrame, left-merge against agg_df on (msname, window_idx) to
# pull in mean_rt for exactly the rows the feature matrix uses. A merge is
# a columnar/vectorized join, not a per-row Python dict lookup.
keys_df = pd.DataFrame(keys, columns=["msname", "window_idx"])
keys_df["window_idx"] = keys_df["window_idx"].astype("int32")
keys_df["msname"] = keys_df["msname"].astype(agg_df["msname"].dtype)  # same categories

merged = keys_df.merge(agg_df, how="left", on=["msname", "window_idx"])
del agg_df, keys_df
gc.collect()

static_scores = np.where(merged["mean_rt"].to_numpy() > static_threshold, 1.0, 0.0)
# rows with no match (shouldn't happen -- every key came from this same
# file -- but guard honestly rather than silently treating NaN as 0)
n_unmatched = int(merged["mean_rt"].isna().sum())
if n_unmatched:
    print(f"  NOTE: {n_unmatched} of {len(merged)} keys had no matching raw row (treated as score 0.0, not flagged).")
del merged
gc.collect()

results["static_slo"] = auc(static_scores, "Static global SLO threshold (binary)")

print()
print("=== Ablations: single-signal and pairwise fits (same AUC metric) ===")
feature_names = ["blast_radius", "latency_z", "callrate_z"]
combos = [
    ([0], "blast_radius only"),
    ([1], "latency_z only (fitted)"),
    ([2], "callrate_z only"),
    ([0, 1], "blast_radius + latency_z"),
    ([0, 2], "blast_radius + callrate_z"),
    ([1, 2], "latency_z + callrate_z"),
    ([0, 1, 2], "all three (= full model, sanity check)"),
]
for idx_list, name in combos:
    Xi = X[:, idx_list]
    sc = StandardScaler()
    Xi_s = sc.fit_transform(Xi)
    m = LogisticRegression()
    m.fit(Xi_s, y)
    scores_i = m.predict_proba(Xi_s)[:, 1]
    val = auc(scores_i, f"Ablation [{name}]")
    results[f"ablation_{'_'.join(map(str, idx_list))}"] = val

print()
print("=== Lead-time check: does the score flag the upstream service BEFORE downstream services show anomaly? ===")
events = state["events"]
for (um, window_idx, count, affected) in events:
    print(f"  Event: {um} at window {window_idx} triggered {count} downstream anomalies: {affected}")
    print(f"    -> upstream '{um}' latency_z at window {window_idx}: {state['latency_z_by_service'].get(um, {}).get(window_idx, 'N/A')}")

with open("data/agg/evaluation_results_v3.pkl", "wb") as f:
    pickle.dump(results, f)
print()
print("Saved evaluation_results_v3.pkl")
