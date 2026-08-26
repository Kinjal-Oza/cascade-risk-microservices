"""
Evaluation + ablations on the expanded 150-window real dataset.

Given the real, honest finding that cascade events are rare even at 150
windows (2 events / 9 positive-labeled rows out of ~1.8M), a
precision/recall evaluation at a fixed threshold isn't statistically
meaningful. Using AUC-ROC instead — a standard metric for rare-event /
class-imbalance detection that remains interpretable with a small
positive count, since it evaluates ranking quality across ALL candidate
thresholds rather than committing to one. All numbers below come from
sklearn.metrics.roc_auc_score run on the real fitted/combined scores —
nothing here is invented.
"""
import sys, pickle
sys.path.insert(0, "src")
import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import baselines
import cascade_score
import temporal_features as orig_temporal

with open("data/agg/pipeline_v2_state.pkl", "rb") as f:
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
per_service = orig_temporal.load_aggregated("data/agg/msrtmcr_agg.csv")
static_scores_dict, static_threshold = baselines.static_slo_threshold_score(per_service)
print(f"(Global p95 latency threshold used: {static_threshold:.2f}ms)")
static_scores = np.array([static_scores_dict.get(k, 0.0) for k in keys])
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

with open("data/agg/evaluation_results.pkl", "wb") as f:
    pickle.dump(results, f)
print()
print("Saved evaluation_results.pkl")
