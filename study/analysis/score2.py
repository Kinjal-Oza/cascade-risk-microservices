"""Score campaign 2 per CAMPAIGN2_PLAN.md (same rules as score_testbed.py; adds M7/M8 and two apps).
Usage: python3 score2.py RUNDIR OUT.json
"""
import sys, os, json, glob, gzip, math, collections
import numpy as np, pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, f"{H}/method_src")
import graph_features as GF, temporal_features_fast as TF, cascade_score as CS, cascade_labeling as CL
D, OUT = sys.argv[1], sys.argv[2]
W, NW, F0, F1 = 30, 22, 240, 540
FRONT = {'social': 'nginx-web-server', 'hotel': 'frontend'}
plans = {a: json.load(open(f"{D}/plan_{a}.json")) for a in ("social", "hotel") if os.path.exists(f"{D}/plan_{a}.json")}

def truth(meta):
    r = pd.read_csv(f"{D}/{meta['run']}.req.csv"); t0 = meta["t0"]
    r["b"] = ((r.t - t0) // W).astype(int); r = r[(r.b >= 0) & (r.b < NW)]
    g = r.groupby("b").agg(p95=("lat_ms", lambda x: x.quantile(.95)), err=("status", lambda s: (s != 200).mean()))
    base = g.p95.loc[0:6].median(); thr = max(5 * base, 100.0)
    breach = (g.p95 > thr) | (g.err > 0.05)
    win = [b for b in g.index if breach[b] and F0 // W <= b <= (F1 + 60) // W - 1]
    return dict(baseline_p95=base, slo=thr, cascade=bool(win), onset_bin=(min(win) if win else None),
                pre_breach=[int(b) for b in g.index if breach[b] and b < F0 // W])

def features(meta):
    c = pd.read_csv(f"{D}/{meta['run']}.cg.csv.gz"); t0 = meta["t0"]
    c["b"] = ((c.timestamp / 1000 - t0) // W).astype(int); c = c[(c.b >= 0) & (c.b < NW)]
    pre = c[(c.b < F0 // W) & (c.um != "USER")]
    graph = collections.defaultdict(collections.Counter)
    for (um, dm), n in pre.groupby(["um", "dm"]).size().items(): graph[um][dm] += int(n)
    blast = GF.blast_radius(graph)
    agg = c.groupby(["dm", "b"]).agg(rt=("rt", "mean"), n=("rt", "size")).reset_index()
    series = {s: [(int(r.b), float(r.rt), float(r.n)) for r in g.itertuples()] for s, g in agg.groupby("dm")}
    lz = {s: TF.latency_deviation_score(v) for s, v in series.items()}
    cz = {s: TF.call_rate_anomaly_score(v) for s, v in series.items()}
    # sliding-window z (M5): previous 10 windows only
    sz = {}
    for s, v in series.items():
        d = {}
        for i in range(len(v)):
            hist = [x[1] for x in v[max(0, i - 10):i]]
            if len(hist) >= 3:
                lh = [math.log1p(max(h, 0)) for h in hist]; mu = np.mean(lh); sd = np.std(lh)
                d[v[i][0]] = (math.log1p(max(v[i][1], 0)) - mu) / (sd + 0.5)
        sz[s] = d
    events = CL.label_cascade_events(graph, lz, z_threshold=3.0, min_downstream=3)
    tz = {}
    rp = f"{D}/{meta['run']}.res.csv"
    if os.path.exists(rp):
        r = pd.read_csv(rp); r["b"] = ((r.t - t0) // W).astype(int); r = r[(r.b >= 0) & (r.b < NW)]
        for svc, g in r.groupby("service"):
            g = g.sort_values("t"); per = g.groupby("b").throttled_usec.agg(["min", "max"])
            ser = [(int(b), float(row["max"] - row["min"]), 0.0) for b, row in per.iterrows()]
            tz[svc] = TF.latency_deviation_score(ser)   # same robust-z formula on log1p(throttled usec per window)
    return dict(blast=blast, series=series, lz=lz, cz=cz, sz=sz, events=events, tz=tz, app=meta["app"])

def _res_name(s):   # call-graph name -> compose service name
    m = {"nginx-web-server": "nginx-thrift", "home-timeline-service-redis": "home-timeline-redis", "user-timeline-service-mongo": "user-timeline-mongodb",
         "user-timeline-service-redis": "user-timeline-redis", "post-storage-service-mongo": "post-storage-mongodb",
         "post-storage-service-memcached": "post-storage-memcached", "social-graph-service-mongo": "social-graph-mongodb",
         "social-graph-service-redis": "social-graph-redis", "url-shorten-service-mongo": "url-shorten-mongodb",
         "url-shorten-service-memcached": "url-shorten-memcached", "user-mention-service-memcached": "user-memcached"}
    return m.get(s, s)

def window_scores(f, method, static_thr=None):
    """run-level score per window = max over services (or binary for M3/M4)"""
    out = {}
    for b in range(NW):
        vals = []
        for s in f["series"]:
            l = f["lz"][s].get(b); c = f["cz"][s].get(b)
            if method == "M1" and l is not None and c is not None: vals.append(CS.naive_combined_score(f["blast"].get(s, 0.0), l, c))
            elif method == "M2" and l is not None: vals.append(l)
            elif method == "M5" and f["sz"][s].get(b) is not None: vals.append(f["sz"][s][b])
            elif method == "M6" and s == FRONT[f["app"]] and l is not None: vals.append(l)
            elif method == "M8" and l is not None and c is not None:
                zt = f["tz"].get(_res_name(s), {}).get(b, 0.0)
                vals.append(1 / (1 + math.exp(-(math.log1p(max(f["blast"].get(s, 0.0), 0)) * 0.1 + max(l, 0) + max(c, 0) + max(zt, 0)) + 5)))
            elif method.startswith("A:") and l is not None and c is not None:   # ablations: subset of signals in naive score
                keep = method[2:]
                vals.append(CS.naive_combined_score(f["blast"].get(s, 0.0) if "b" in keep else 0.0, l if "l" in keep else 0.0, c if "c" in keep else 0.0))
        if method == "M7":
            vals = [d[b] for d in f["tz"].values() if b in d]
        if method == "M3":
            vals = [1.0 if any(rt > static_thr for (bb, rt, n) in f["series"][s] if bb == b) else 0.0 for s in f["series"]]
        if method == "M4":
            vals = [1.0 if any(e[1] == b for e in f["events"]) else 0.0]
        if vals: out[b] = max(vals)
    return out

runs = []; calib = set()
for app, plan in plans.items():
    nn = []
    for i, (fault, tgt, rep) in enumerate(plan):
        rid = f"{app}_r{i:03d}_{fault}_{tgt}_{rep}"
        if not os.path.exists(f"{D}/{rid}.json"): continue
        meta = json.load(open(f"{D}/{rid}.json")); runs.append((rid, meta))
        if fault == "none": nn.append(rid)
    calib |= set(nn[:4])
print("runs", len(runs), "calibration", len(calib))
T = {rid: truth(m) for rid, m in runs}; Fe = {rid: features(m) for rid, m in runs}
allrt = [rt for rid in calib for s, v in Fe[rid]["series"].items() for (b, rt, n) in v]
static_thr = float(np.percentile(allrt, 95)) if allrt else None
METHODS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "A:b", "A:l", "A:c", "A:bl", "A:bc", "A:lc"]
res = dict(n_runs=len(runs), calibration=sorted(calib), static_thr=static_thr, truth=T, methods={})
for M in METHODS:
    S = {rid: window_scores(Fe[rid], M, static_thr) for rid, m in runs}
    tau = 0.5 if M in ("M3", "M4") else max([v for rid in calib for b, v in S[rid].items() if b >= 3] or [float("inf")])
    det, lead, fa_alerts, fa_hours, mx, lab = 0, [], 0, 0.0, [], []
    ncas = 0
    for rid, m in runs:
        if rid in calib: continue
        al = sorted(b for b, v in S[rid].items() if v > tau and b >= 3)
        ctl_end = NW if m["fault"] == "none" else F0 // W
        fa_alerts += sum(1 for b in al if b < ctl_end); fa_hours += ctl_end * W / 3600
        if m["fault"] != "none":
            t = T[rid]
            mx.append(max([v for b, v in S[rid].items() if F0 // W <= b < F1 // W + 2] or [0])); lab.append(int(t["cascade"]))
            if t["cascade"]:
                ncas += 1; hit = [b for b in al if F0 // W <= b <= t["onset_bin"] + 2]
                if hit: det += 1; lead.append((t["onset_bin"] - hit[0]) * W)
    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(lab, mx) if len(set(lab)) == 2 else None
    res["methods"][M] = dict(tau=tau, cascades=ncas, detected=det, median_lead_s=float(np.median(lead)) if lead else None,
                             lead_s=lead, false_alarms=fa_alerts, control_hours=round(fa_hours, 2),
                             fa_per_hour=round(fa_alerts / fa_hours, 2) if fa_hours else None, auc_cascade_vs_nocascade=auc)
    print(M, {k: v for k, v in res["methods"][M].items() if k != "lead_s"})
json.dump(res, open(OUT, "w"), indent=1, default=float)
