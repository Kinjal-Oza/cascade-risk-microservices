"""Alibaba v2022 re-pull (windows 0-499), reproduction of the paper's pipeline, and the forward evaluation in ALIBABA_PLAN.md."""
import os, sys, glob, csv, subprocess, collections, statistics, shutil, json, time, pickle, gc, math
from concurrent.futures import ProcessPoolExecutor
W = "/kaggle/working"; T = "/kaggle/tmp" if os.path.isdir("/kaggle/tmp") else "/tmp"
BASE = "https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2022MicroservicesTraces"
N = int(os.environ.get("NWIN", "500"))
src = os.path.dirname(glob.glob("/kaggle/input/**/cascade_labeling.py", recursive=True)[0])
R = f"{W}/crs"; os.makedirs(f"{R}/src", exist_ok=True); os.makedirs(f"{R}/data/agg", exist_ok=True)
for f in glob.glob(f"{src}/*.py"):
    shutil.copy(f, f"{R}/src/" if not os.path.basename(f).startswith("run_") else R)
os.makedirs(f"{T}/a", exist_ok=True)

def get(kind, idx):
    p = f"{T}/a/{kind}_{idx}.tar.gz"
    for k in range(6):
        if subprocess.run(["curl", "-sf", "--max-time", "900", "-o", p, f"{BASE}/{kind}/{kind}_{idx}.tar.gz"]).returncode == 0: return p
        time.sleep(10)
    return None

def mcr(idx):
    p = get("MCRRTUpdate", idx)
    if p is None: return idx, None
    per = {}
    proc = subprocess.Popen(["tar", "-xzOf", p], stdout=subprocess.PIPE, text=True)
    r = csv.reader(proc.stdout); next(r)
    for row in r:
        try:
            ms = row[1]; rt = max(float(row[4]), float(row[6])); m = float(row[5]) + float(row[7])
        except Exception: continue
        d = per.setdefault(ms, [0.0, -1e18, 0.0, 0])
        d[0] += rt; d[1] = max(d[1], rt); d[2] += m; d[3] += 1
    proc.wait(); os.remove(p)
    return idx, [f"{idx},{ms},{d[0]/d[3]:.4f},{d[1]:.4f},{d[2]/d[3]:.6f},{d[3]}" for ms, d in per.items()]

def cg(idx):
    p = get("CallGraph", idx)
    if p is None: return idx, None
    c = collections.Counter()
    proc = subprocess.Popen(["tar", "-xzOf", p], stdout=subprocess.PIPE, text=True)
    r = csv.reader(proc.stdout); next(r)
    for row in r:
        try: _, _, _, _, _, um, _, _, dm, _, _ = row
        except ValueError: continue
        if um in ("UNKNOWN", "USER"): continue
        c[(um, dm)] += 1
    proc.wait(); os.remove(p)
    return idx, c

missing = {"mcr": [], "cg": []}
if not os.path.exists(f"{R}/data/agg/msrtmcr_agg.csv"):
    t0 = time.time()
    with open(f"{R}/data/agg/msrtmcr_agg.csv", "w") as out, ProcessPoolExecutor(4) as ex:
        out.write("window_idx,msname,mean_rt,max_rt,mean_mcr,n_samples\n")
        for idx, lines in ex.map(mcr, range(N)):
            if lines is None: missing["mcr"].append(idx); continue
            out.write("\n".join(lines) + "\n")
            if idx % 25 == 0: print("mcr", idx, f"{time.time()-t0:.0f}s", flush=True)
    edges = collections.Counter()
    with ProcessPoolExecutor(4) as ex:
        for idx, c in ex.map(cg, range(N)):
            if c is None: missing["cg"].append(idx); continue
            edges.update(c)
            if idx % 25 == 0: print("cg", idx, f"{time.time()-t0:.0f}s", flush=True)
    with open(f"{R}/data/agg/callgraph_edges_matched.csv", "w") as f:
        f.write("um,dm,call_count\n")
        for (um, dm), n in edges.items(): f.write(f"{um},{dm},{n}\n")
    del edges; gc.collect()
json.dump(missing, open(f"{W}/missing.json", "w"))
print("missing", missing, flush=True)

# 1. reproduction, unchanged scripts
for s in ("run_pipeline_v3.py", "run_evaluation_v3b.py"):
    with open(f"{W}/{s}.log", "w") as lg:
        subprocess.run([sys.executable, s], cwd=R, stdout=lg, stderr=subprocess.STDOUT)
    print(open(f"{W}/{s}.log").read()[-3000:], flush=True)

# 3. forward evaluation
sys.path.insert(0, f"{R}/src")
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score
import cascade_score
st = pickle.load(open(f"{R}/data/agg/pipeline_v3_state.pkl", "rb"))
X = np.asarray(st["X"]); keys = st["keys"]; labels = st["cascade_label_keys"]
lab_by_svc = collections.defaultdict(set)
for s, w in labels: lab_by_svc[s].add(w)
svc = np.array([k[0] for k in keys], dtype=object); win = np.array([k[1] for k in keys], dtype=np.int32)
cur = np.array([w in lab_by_svc.get(s, ()) for s, w in keys])
fut = np.array([any((w + d) in lab_by_svc.get(s, ()) for d in (1, 2, 3)) for s, w in keys])
keep = ~cur
naive = np.array([cascade_score.naive_combined_score(*r) for r in X])
# sliding-window latency z (previous 10 windows), from the aggregated file
agg = pd.read_csv(f"{R}/data/agg/msrtmcr_agg.csv", usecols=["window_idx", "msname", "mean_rt"],
                  dtype={"window_idx": "int32", "msname": "category", "mean_rt": "float32"}).sort_values(["msname", "window_idx"])
agg["l"] = np.log1p(agg.mean_rt.clip(lower=0))
g = agg.groupby("msname", observed=True)["l"]
mu = g.transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean()); sd = g.transform(lambda s: s.shift(1).rolling(10, min_periods=3).std(ddof=0))
agg["sz"] = (agg.l - mu) / (sd + 0.5)
thr = float(np.sort(agg.mean_rt.to_numpy())[int(len(agg) * 0.95)])
kd = pd.DataFrame({"msname": svc, "window_idx": win}); kd["msname"] = kd.msname.astype(agg.msname.dtype)
m = kd.merge(agg[["msname", "window_idx", "sz", "mean_rt"]], how="left", on=["msname", "window_idx"])
sz = m.sz.fillna(-99).to_numpy(); static = (m.mean_rt.to_numpy() > thr).astype(float)
yk = fut[keep]
out = dict(rows=int(keep.sum()), positives=int(yk.sum()), current_labelled_excluded=int(cur.sum()))
for name, sc in [("naive_crs", naive), ("latency_z", X[:, 1]), ("callrate_z", X[:, 2]), ("blast_radius", X[:, 0]),
                 ("sliding_latency_z", sz), ("static_threshold", static)]:
    s = sc[keep]; out[name] = dict(auc_roc=float(roc_auc_score(yk, s)), auc_pr=float(average_precision_score(yk, s)))
q = float(np.quantile(naive, 0.999)); ev = []
for (um, w, n, aff) in st["events"]:
    hits = [d for d in (3, 2, 1) if any((s == um and ww == w - d and naive[i] >= q) for i, (s, ww) in [(i, keys[i]) for i in np.where(svc == um)[0]])]
    ev.append(dict(um=um, window=int(w), warned_windows_ahead=max(hits) if hits else 0))
out["events"] = ev; out["top0.1pct_naive_threshold"] = q; out["base_rate"] = float(yk.mean())
json.dump(out, open(f"{W}/forward_eval.json", "w"), indent=1); print(json.dumps(out, indent=1))
shutil.rmtree(f"{R}/data/agg/cg_windows", ignore_errors=True)
for f in ("msrtmcr_agg.csv",):
    subprocess.run(f"gzip -c {R}/data/agg/{f} > {W}/{f}.gz", shell=True)
shutil.copy(f"{R}/data/agg/callgraph_edges_matched.csv", W)
os.remove(f"{R}/data/agg/pipeline_v3_state.pkl"); print("DONE", flush=True)
