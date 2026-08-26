"""
Two honesty checks requested by Kinjal before trusting the "fitted beats
naive" question either way, run on the real 500-window data
(pipeline_v3_state.pkl):

  #1 Leave-one-event-out cross-validation. The reported 0.8267 AUC for the
     fitted Cascade Risk Score was computed on the SAME data it was fit
     on -- an in-sample number, which can look better than the model
     really performs on genuinely new data. LOEO refits the model 8 times,
     each time holding out ALL rows belonging to one of the 8 real
     cascade events (never seen during that fold's fit) and scoring AUC
     only on that held-out event's positives against the full negative
     background. This tests: does the model still rank a genuinely-new
     event above ~8.5M negatives, or does its in-sample number partly
     reflect having seen that exact event's rows during fitting?

  #2 Paired bootstrap significance test on the naive-vs-fitted AUC gap
     (0.8360 vs 0.8267 in-sample). Resamples the 31 real positive rows
     (with replacement) and a large random subsample of negatives (with
     replacement) many times, computing both AUCs each time, to see how
     often naive actually outscores fitted under resampling -- i.e.
     whether the 0.0093 gap is a real, stable pattern or noise from
     having only 31 positive examples.

No formulas, thresholds, or labels changed -- same real data, same real
scores, just evaluated more rigorously than the single in-sample number.
"""
import sys, pickle, time
sys.path.insert(0, "src")
import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import cascade_score

t0 = time.time()
with open("data/agg/pipeline_v3_state.pkl", "rb") as f:
    state = pickle.load(f)

X = np.array(state["X"])
y = np.array(state["y"])
keys = state["keys"]
events = state["events"]
print(f"Loaded: {len(y)} rows, {int(y.sum())} positives. ({time.time()-t0:.1f}s)")

# ---- map each positive row to its event (windows are all distinct across
# the 8 real events found, so window value alone identifies the event) ----
event_windows = [w for (_um, w, _count, _affected) in events]
assert len(event_windows) == len(set(event_windows)), "events share a window -- LOEO-by-window assumption breaks"
window_to_event = {w: i for i, w in enumerate(event_windows)}
print(f"Events: {len(events)}, at windows {sorted(event_windows)}")

window_arr = np.array([k[1] for k in keys], dtype=np.int32)
pos_idx = np.where(y == 1)[0]
neg_idx = np.where(y == 0)[0]
row_event_id = np.full(len(y), -1, dtype=np.int8)
for i in pos_idx:
    row_event_id[i] = window_to_event[window_arr[i]]
print(f"Positive rows per event: {[int((row_event_id == e).sum()) for e in range(len(events))]}")

print()
print("=== #1 Leave-one-event-out cross-validation (out-of-sample AUC) ===")
loeo_results = []
for e in range(len(events)):
    test_pos_mask = row_event_id == e
    train_mask = ~test_pos_mask  # everything except this event's positive rows (all negatives + other 7 events' positives)
    X_train, y_train = X[train_mask], y[train_mask]
    n_train_pos = int(y_train.sum())
    if n_train_pos < 3:
        print(f"  Event {e} (window {event_windows[e]}): skipped, only {n_train_pos} positives left to train on")
        continue
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    model = LogisticRegression()
    model.fit(X_train_s, y_train)

    # test set: this event's held-out positive rows + ALL negative rows
    test_mask = test_pos_mask | (y == 0)
    X_test_s = scaler.transform(X[test_mask])
    y_test = y[test_mask]
    scores_test = model.predict_proba(X_test_s)[:, 1]
    fold_auc = roc_auc_score(y_test, scores_test)
    n_test_pos = int(test_pos_mask.sum())
    loeo_results.append(fold_auc)
    print(f"  Event {e} (window {event_windows[e]}, {n_test_pos} held-out positive rows, trained on {n_train_pos} positives): out-of-sample AUC = {fold_auc:.4f} ({time.time()-t0:.0f}s elapsed)")

loeo_mean = float(np.mean(loeo_results))
loeo_std = float(np.std(loeo_results))
print(f"\nLOEO mean out-of-sample AUC: {loeo_mean:.4f} (std across folds: {loeo_std:.4f}, n_folds={len(loeo_results)})")
print(f"Compare to in-sample (fit-and-evaluate-on-everything) AUC: 0.8267")
print(f"Compare to naive (unfitted, no train/test split needed): 0.8360")

print()
print("=== #2 Paired bootstrap: how often does naive actually beat fitted? ===")
# Refit the full in-sample model once (same as run_evaluation_v3b.py) to get
# per-row scores for both methods, then bootstrap-resample from those
# precomputed scores -- no refitting inside the loop, just resampling.
scaler_full = StandardScaler()
X_scaled_full = scaler_full.fit_transform(X)
model_full = LogisticRegression()
model_full.fit(X_scaled_full, y)
scores_fitted = model_full.predict_proba(X_scaled_full)[:, 1]
scores_naive = np.array([cascade_score.naive_combined_score(*row) for row in X])
print(f"In-sample AUC check -- fitted: {roc_auc_score(y, scores_fitted):.4f}, naive: {roc_auc_score(y, scores_naive):.4f} ({time.time()-t0:.0f}s elapsed)")

N_BOOT = 1000
NEG_SUBSAMPLE = 300_000
rng = np.random.default_rng(12345)  # fixed seed -- reproducible, not cherry-picked after seeing results

diffs = np.empty(N_BOOT)
naive_wins = 0
for b in range(N_BOOT):
    boot_pos = rng.choice(pos_idx, size=len(pos_idx), replace=True)
    boot_neg = rng.choice(neg_idx, size=NEG_SUBSAMPLE, replace=True)
    boot_idx = np.concatenate([boot_pos, boot_neg])
    y_boot = y[boot_idx]
    if y_boot.sum() == 0 or y_boot.sum() == len(y_boot):
        continue  # degenerate resample, skip (rare)
    auc_fitted_b = roc_auc_score(y_boot, scores_fitted[boot_idx])
    auc_naive_b = roc_auc_score(y_boot, scores_naive[boot_idx])
    diffs[b] = auc_naive_b - auc_fitted_b
    if auc_naive_b > auc_fitted_b:
        naive_wins += 1
    if (b + 1) % 200 == 0:
        print(f"  bootstrap {b+1}/{N_BOOT} ({time.time()-t0:.0f}s elapsed)")

mean_diff = float(np.mean(diffs))
ci_low, ci_high = float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))
pct_naive_wins = 100.0 * naive_wins / N_BOOT

print(f"\nBootstrap mean(naive AUC - fitted AUC): {mean_diff:.4f}")
print(f"95% CI on the difference: [{ci_low:.4f}, {ci_high:.4f}]")
print(f"Naive beat fitted in {naive_wins}/{N_BOOT} bootstrap resamples ({pct_naive_wins:.1f}%)")
if ci_low > 0:
    print("-> The 95% CI excludes zero: naive genuinely, consistently outperforms fitted on this data, not just a one-sample fluke.")
elif ci_high < 0:
    print("-> The 95% CI excludes zero the OTHER way: fitted genuinely outperforms naive -- opposite of the in-sample reading.")
else:
    print("-> The 95% CI includes zero: cannot confidently say either one beats the other -- the in-sample gap may just be noise.")

with open("data/agg/cv_significance_results.pkl", "wb") as f:
    pickle.dump({
        "loeo_results": loeo_results, "loeo_mean": loeo_mean, "loeo_std": loeo_std,
        "bootstrap_diffs": diffs, "bootstrap_ci": (ci_low, ci_high),
        "pct_naive_wins": pct_naive_wins, "mean_diff": mean_diff,
    }, f)
print(f"\nSaved data/agg/cv_significance_results.pkl. Total time: {time.time()-t0:.0f}s")
