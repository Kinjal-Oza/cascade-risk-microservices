"""EXPLORATORY (review request): operating-point precision and row/event mapping for the Alibaba forward task.
Needs data/agg/pipeline_v3_state.pkl from run_pipeline_v3.py (regenerated locally from the published aggregates).
Usage: python3 operating_points.py CRS_DIR OUT.json"""
import sys, pickle, json, collections, numpy as np
R, OUT = sys.argv[1], sys.argv[2]; sys.path.insert(0, f"{R}/src")
import cascade_score
from sklearn.metrics import roc_auc_score, average_precision_score
st = pickle.load(open(f"{R}/data/agg/pipeline_v3_state.pkl", "rb"))
X = np.asarray(st["X"]); keys = st["keys"]; labels = st["cascade_label_keys"]; events = st["events"]
lab = collections.defaultdict(set)
for s, w in labels: lab[s].add(w)
svc = np.array([k[0] for k in keys], dtype=object); win = np.array([k[1] for k in keys], dtype=np.int32)
cur = np.array([w in lab.get(s, ()) for s, w in keys]); fut = np.array([any((w + d) in lab.get(s, ()) for d in (1, 2, 3)) for s, w in keys])
keep = ~cur; y = fut[keep]
naive = np.array([cascade_score.naive_combined_score(*r) for r in X])
scores = {"naive_crs": naive, "latency_z": X[:, 1], "blast_radius": X[:, 0]}
nwin = len(set(win.tolist())); hours = nwin * 3 / 60
out = dict(rows_scored=int(len(keys)), rows_forward=int(keep.sum()), windows=nwin, hours=hours, services=int(len(set(svc.tolist()))),
           events=len(events), same_window_label_rows=int(cur.sum()), forward_positive_rows=int(y.sum()))
# row/event mapping: which event(s) each forward-positive row anticipates
ev_rows = collections.Counter(); upstream_rows = 0
evset = {(um, w): (um, w, n, aff) for (um, w, n, aff) in events}
for i in np.where(keep & fut)[0]:
    s, w = keys[i]
    for (um, ew, n, aff) in events:
        if ew - w in (1, 2, 3) and (s == um or s in set(aff)): ev_rows[f"{um}@{ew}"] += 1; upstream_rows += int(s == um)
out["forward_rows_per_event"] = dict(ev_rows); out["forward_rows_that_are_event_upstream"] = upstream_rows
out["event_sizes"] = [dict(upstream=um, window=int(w), callees_deviating=int(n)) for (um, w, n, aff) in events]
out["auc_check"] = {k: float(roc_auc_score(y, v[keep])) for k, v in scores.items()}
ops = {}
for name, sc in scores.items():
    s = sc[keep]; ops[name] = []
    for frac in (1e-4, 1e-3, 1e-2, 5e-2):
        thr = np.quantile(s, 1 - frac); flag = s >= thr
        tp = int((flag & y).sum()); fl = int(flag.sum())
        ev_hit = 0
        for (um, w, n, aff) in events:
            idx = np.where((svc == um) & (win >= w - 3) & (win <= w - 1))[0]
            ev_hit += int(any(sc[i] >= thr for i in idx))
        ops[name].append(dict(top_fraction=frac, threshold=float(thr), flagged_rows=fl, flagged_per_hour=fl / hours, true_positive_rows=tp,
                              precision=tp / max(fl, 1), recall_rows=tp / max(int(y.sum()), 1), events_warned_1to3_ahead=ev_hit))
out["operating_points"] = ops
json.dump(out, open(OUT, "w"), indent=1); print(json.dumps(out, indent=1)[:5000])
