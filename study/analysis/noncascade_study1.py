"""EXPLORATORY: why Study-1 cpu_step, cpu_ramp and surge runs rarely breached. Ratio of fault-window to pre-fault
frontend p95 and target-service mean response time (from sampled call records)."""
import sys, json, gzip, numpy as np, pandas as pd, collections
D = sys.argv[1]; plan = json.load(open(f"{D}/plan.json")); F0, F1 = 240, 420
res = collections.defaultdict(lambda: dict(p95_ratio=[], target_rt_ratio=[], max_p95_ms=[]))
for i, (f, t, r) in enumerate(plan):
    rid = f"r{i:03d}_{f}_{t}_{r}"
    try: m = json.load(open(f"{D}/{rid}.json"))
    except FileNotFoundError: continue
    if f == "none": continue
    q = pd.read_csv(f"{D}/{rid}.req.csv"); q["s"] = q.t - m["t0"]
    pre = q[(q.s >= 30) & (q.s < F0)].lat_ms.quantile(.95)
    bins = q[(q.s >= F0) & (q.s < F1)].groupby((q.s // 30)).lat_ms.quantile(.95)
    res[f]["p95_ratio"].append(float(bins.max() / pre)); res[f]["max_p95_ms"].append(float(bins.max()))
    if t not in (None, "none", "None"):
        c = pd.read_csv(f"{D}/{rid}.cg.csv.gz"); c["s"] = c.timestamp / 1000 - m["t0"]; c = c[c.dm == t]
        a, b = c[(c.s >= 30) & (c.s < F0)].rt.mean(), c[(c.s >= F0) & (c.s < F1)].groupby(c.s // 30).rt.mean().max()
        if a and a > 0: res[f]["target_rt_ratio"].append(float(b / a))
out = {f: {k: dict(median=float(np.median(v)), p90=float(np.percentile(v, 90)), max=float(max(v))) for k, v in d.items() if v} for f, d in res.items()}
json.dump(out, open("../results/noncascade_study1.json", "w"), indent=1)
for f, d in out.items(): print(f, d)
