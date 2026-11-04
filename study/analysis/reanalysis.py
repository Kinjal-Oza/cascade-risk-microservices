"""EXPLORATORY re-analysis requested in review (not pre-registered). Uses the pre-registered scorer's own functions.
Usage: python3 reanalysis.py STUDY RUNDIR OUT.json      STUDY in {1,2}
Outputs (all per study):
  paired      : per-cascade lead differences M1-M6, M2-M6, M5-M6, M1int-M6 (internal services only), with target-cluster bootstrap
  budget      : coverage of early warning vs held-out false alarms, thresholds from calibration-score quantiles only
  incidents   : false alarms counted as windows and as de-duplicated incidents (consecutive alert windows merged)
  local       : share of local-fault runs with an alert in the fault window
  w10         : detectors at 10-s and 15-s windows, ground truth unchanged (30-s bins)
  endpoint    : latency- vs error-triggered breaches; services deviating at onset (propagation)
  slo         : cascade counts and M1-M6 ties under alternative SLO rules
  rates       : achieved request rate, error rate, injection verification
  samples     : per-service calls per window (10% trace sampling)
"""
import sys, os, json, math, collections
import numpy as np, pandas as pd
STUDY, RUNDIR, OUT = int(sys.argv[1]), sys.argv[2], sys.argv[3]
H = os.path.dirname(os.path.abspath(__file__))
src = open(f"{H}/score2.py").read().split("runs = []; calib = set()")[0]
G = {"__file__": f"{H}/score2.py", "__name__": "score2"}; sys.argv = ["score2.py", RUNDIR, "/dev/null"]; exec(compile(src, "score2.py", "exec"), G)
TF, CS, CL, GF = G["TF"], G["CS"], G["CL"], G["GF"]
if STUDY == 1:
    F0, F1, END = 240, 420, 540; plans = {"social": json.load(open(f"{RUNDIR}/plan.json"))}; prefix = lambda a, i, f, t, r: f"r{i:03d}_{f}_{t}_{r}"; ncal = 8
else:
    F0, F1, END = 240, 540, 660; plans = G["plans"]; prefix = lambda a, i, f, t, r: f"{a}_r{i:03d}_{f}_{t}_{r}"; ncal = 4
FRONT = {"social": "nginx-web-server", "hotel": "frontend"}
runs, calib = [], set()
for app, plan in plans.items():
    nn = []
    for i, (f, t, r) in enumerate(plan):
        rid = prefix(app, i, f, t, r)
        if not os.path.exists(f"{RUNDIR}/{rid}.json"): continue
        m = json.load(open(f"{RUNDIR}/{rid}.json")); m.setdefault("app", app); runs.append((rid, m))
        if f == "none": nn.append(rid)
    calib |= set(nn[:ncal])

def set_window(w):
    G["W"] = w; G["NW"] = int(math.ceil(END / w)); G["F0"] = F0; G["F1"] = F1

def truth(m, mult=5, floor=100.0, bs=30):
    r = pd.read_csv(f"{RUNDIR}/{m['run']}.req.csv"); r["b"] = ((r.t - m["t0"]) // bs).astype(int); r = r[(r.b >= 0) & (r.b < int(math.ceil(END / bs)))]
    g = r.groupby("b").agg(p95=("lat_ms", lambda x: x.quantile(.95)), err=("status", lambda s: (s != 200).mean()), n=("lat_ms", "size"))
    base = g.p95.loc[0:int(210 / bs)].median(); thr = max(mult * base, floor)
    lat = g.p95 > thr; err = g.err > 0.05; br = lat | err
    win = [b for b in g.index if br[b] and F0 // bs <= b <= (F1 + 60) // bs - 1]
    on = min(win) if win else None
    return dict(cascade=bool(win), onset_s=(on * bs if on is not None else None), slo=thr, base=base,
                trig=(None if on is None else ("both" if lat[on] and err[on] else "latency" if lat[on] else "error")),
                rate=float(g.n.loc[0:int(210 / bs)].mean() / bs), err_pre=float(g.err.loc[0:int(210 / bs)].mean()))

def scores(f, M, static_thr=None):
    if M in ("M1int", "M2int"):   # internal services only: drop the frontend series
        fr = FRONT[f["app"]]; g = dict(f); g["series"] = {k: v for k, v in f["series"].items() if k != fr}
        return G["window_scores"](g, M[:2], static_thr)
    return G["window_scores"](f, M, static_thr)

METH = ["M1", "M2", "M5", "M6", "M8", "M1int", "M2int"] if STUDY == 2 else ["M1", "M2", "M5", "M6", "M1int", "M2int"]
def run_all(w, quantiles=None):
    set_window(w); T = {rid: truth(m) for rid, m in runs}; Fe = {rid: G["features"](m) for rid, m in runs}
    S = {M: {rid: scores(Fe[rid], M) for rid, m in runs} for M in METH}
    return T, Fe, S

def alerts(sc, tau, w, lo): return sorted(b * w for b, v in sc.items() if v > tau and b >= lo)
def evaluate(T, S, w, tau_by=None, qs=None):
    lo = int(math.ceil(90 / w))   # same 3-window (90-s) minimum history as the pre-registered 30-s scoring
    res = {}
    for M in METH:
        cal = [v for rid in calib for b, v in S[M][rid].items() if b * w >= lo * w]
        taus = {"prereg": max(cal)} if qs is None else {q: float(np.quantile(cal, q)) for q in qs}
        res[M] = {}
        for key, tau in taus.items():
            lead, fa_w, fa_inc, hours, loc_alert, nloc = {}, 0, 0, 0.0, 0, 0
            for rid, m in runs:
                if rid in calib: continue
                al = alerts(S[M][rid], tau, w, lo); ctl_end = END if m["fault"] == "none" else F0
                ca = [a for a in al if a < ctl_end]; fa_w += len(ca); fa_inc += sum(1 for i, a in enumerate(ca) if i == 0 or a - ca[i - 1] > w)
                hours += ctl_end / 3600   # same exposure definition as the pre-registered scorer
                if m["fault"] == "none": continue
                t = T[rid]; fw = [a for a in al if F0 <= a]
                if t["cascade"]:
                    hit = [a for a in fw if a <= t["onset_s"] + 60]; lead[rid] = (t["onset_s"] - hit[0]) if hit else None
                else:
                    nloc += 1; loc_alert += int(any(a < F1 + 60 for a in fw))
            L = [v for v in lead.values() if v is not None]
            res[M][str(key)] = dict(tau=tau, lead=lead, detected=len(L), early=sum(1 for v in L if v > 0), median_lead=float(np.median(L)) if L else None,
                                    fa_windows_h=fa_w / hours, fa_incidents_h=fa_inc / hours, local_alert_share=loc_alert / max(nloc, 1), control_h=hours)
    return res

def target_of(rid): return rid.split("_")[-2] if STUDY == 1 else "_".join(rid.split("_")[:1] + rid.split("_")[-2:-1])
def paired(res, a, b, key="prereg", B=5000, seed=7):
    la, lb = res[a][key]["lead"], res[b][key]["lead"]
    rids = [r for r in la if la[r] is not None and lb.get(r) is not None]
    d = np.array([la[r] - lb[r] for r in rids]); groups = collections.defaultdict(list)
    for r, x in zip(rids, d): groups[target_of(r)].append(x)
    keys = list(groups); rng = np.random.default_rng(seed); means, net = [], []
    for _ in range(B):
        s = np.concatenate([groups[k] for k in rng.choice(keys, len(keys))]); means.append(s.mean()); net.append(((s > 0).sum() - (s < 0).sum()) / len(s))
    return dict(n=len(d), ties=int((d == 0).sum()), a_earlier=int((d > 0).sum()), b_earlier=int((d < 0).sum()),
                diffs=sorted(d.tolist()), mean=float(d.mean()), mean_ci=[float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))],
                net_share=float(((d > 0).sum() - (d < 0).sum()) / len(d)), net_ci=[float(np.percentile(net, 2.5)), float(np.percentile(net, 97.5))],
                a_ahead_ge30=int((d >= 30).sum()), a_ahead_ge60=int((d >= 60).sum()), clusters=len(keys), bootstrap="resample target groups, 5000 draws, percentile 95% CI, seed 7")

runs_d = dict(runs)
out = {"study": STUDY, "calibration": sorted(calib)}
T, Fe, S = run_all(30); R = evaluate(T, S, 30)
out["prereg_check"] = {M: {k: v for k, v in R[M]["prereg"].items() if k != "lead"} for M in METH}
out["paired"] = {f"{a}-M6": paired(R, a, "M6") for a in METH if a != "M6"}
qs = [0.90, 0.95, 0.98, 0.99, 0.995, 0.999, 1.0]
RB = evaluate(T, S, 30, qs=qs)
out["budget"] = {M: [{"q": q, **{k: v for k, v in RB[M][str(q)].items() if k != "lead"}} for q in qs] for M in METH}
# endpoint / propagation
cas = [rid for rid, m in runs if rid not in calib and T[rid]["cascade"]]
out["endpoint"] = dict(trigger=dict(collections.Counter(T[r]["trig"] for r in cas)))
for name, thr in (("z3", 3.0), ("above_M2_tau", R["M2"]["prereg"]["tau"])):
    dev, first_is_target = [], []
    for rid in cas:
        on = T[rid]["onset_s"] // 30; f = Fe[rid]; fr = FRONT[runs_d[rid]["app"]]
        hot = [s for s in f["lz"] if s != fr and (f["lz"][s].get(on, -9) > thr or f["lz"][s].get(on - 1, -9) > thr)]
        dev.append(len(hot))
    out["endpoint"][f"internal_services_{name}_at_onset"] = dict(threshold=thr, median=float(np.median(dev)), min=int(min(dev)), max=int(max(dev)),
                                                               share_ge1=float(np.mean(np.array(dev) >= 1)), share_ge2=float(np.mean(np.array(dev) >= 2)), share_ge3=float(np.mean(np.array(dev) >= 3)))
# SLO sensitivity (alerts fixed at pre-registered thresholds)
slo = {}
for mult in (3, 5, 10):
    for floor in (50.0, 100.0, 200.0):
        TT = {rid: truth(m, mult, floor) for rid, m in runs}; n = sum(1 for r, m in runs if r not in calib and m["fault"] != "none" and TT[r]["cascade"])
        ties = tot = m1e = m6e = 0
        for rid, m in runs:
            if rid in calib or m["fault"] == "none" or not TT[rid]["cascade"]: continue
            def ld(M):
                al = [a for a in alerts(S[M][rid], R[M]["prereg"]["tau"], 30, 3) if F0 <= a <= TT[rid]["onset_s"] + 60]; return (TT[rid]["onset_s"] - al[0]) if al else None
            x, y = ld("M1"), ld("M6")
            if x is None or y is None: continue
            tot += 1; ties += int(x == y); m1e += int(x > y); m6e += int(y > x)
        slo[f"{mult}x/{int(floor)}ms"] = dict(cascades=n, paired=tot, ties=ties, crs_earlier=m1e, frontend_earlier=m6e)
out["slo"] = slo
out["slo_dominance"] = dict(floor_dominates=int(sum(1 for r, m in runs if T[r]["slo"] == 100.0)), runs=len(runs),
                            base_p95_by_app={a: float(np.median([T[r]["base"] for r, m in runs if m["app"] == a])) for a in plans})
# rates and injection verification
rates = [T[r]["rate"] for r, m in runs]; ev_rc = collections.Counter()
for rid, m in runs:
    for e in m.get("events", []):
        if "rc=" in str(e[0]): ev_rc[str(e[0]).split("rc=")[1]] += 1
out["rates"] = dict(req_per_s_median=float(np.median(rates)), min=float(min(rates)), max=float(max(rates)),
                    pre_fault_error_rate_max=float(max(T[r]["err_pre"] for r, m in runs)), injection_rc=dict(ev_rc))
# per-service samples per window
cnt = [n for rid, m in runs[:40] for s, v in Fe[rid]["series"].items() for (b, rt, n) in v]
out["samples_per_30s_window"] = dict(median=float(np.median(cnt)), p10=float(np.percentile(cnt, 10)), p90=float(np.percentile(cnt, 90)))
# per app x fault x target
tab = collections.defaultdict(lambda: dict(runs=0, cascades=0, m1=[], m6=[]))
for rid, m in runs:
    if rid in calib or m["fault"] == "none": continue
    k = f"{m['app']}|{m['fault']}|{m.get('target')}"; tab[k]["runs"] += 1
    if T[rid]["cascade"]:
        tab[k]["cascades"] += 1; tab[k]["m1"].append(R["M1"]["prereg"]["lead"][rid]); tab[k]["m6"].append(R["M6"]["prereg"]["lead"][rid])
out["per_target"] = tab
# finer detector windows (ground truth unchanged)
out["finer"] = {}
for w in (10, 15):
    T2, Fe2, S2 = run_all(w); T2 = T; R2 = evaluate(T2, S2, w)
    out["finer"][str(w)] = dict(paired={f"{a}-M6": paired(R2, a, "M6") for a in ("M1", "M2", "M1int")},
                                summary={M: {k: v for k, v in R2[M]["prereg"].items() if k != "lead"} for M in METH})
    cnt = [n for rid, m in runs[:40] for s, v in Fe2[rid]["series"].items() for (b, rt, n) in v]
    out["finer"][str(w)]["samples_per_window"] = dict(median=float(np.median(cnt)), p10=float(np.percentile(cnt, 10)))
json.dump(out, open(OUT, "w"), indent=1, default=lambda o: o if not isinstance(o, np.generic) else o.item())
print(json.dumps({k: out[k] for k in ("paired", "endpoint", "slo", "rates")}, indent=1, default=str)[:6000])
