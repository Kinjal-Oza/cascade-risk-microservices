"""EXPLORATORY: share of service-windows without a score (no sampled call), Study 2, all runs, 30-s windows."""
import sys, os, json, glob, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); D = sys.argv[1]
src = open(f"{H}/score2.py").read().split("runs = []; calib = set()")[0]
G = {"__file__": f"{H}/score2.py"}; sys.argv = ["x", D, "/dev/null"]; exec(compile(src, "score2.py", "exec"), G)
tot = miss = 0; fmiss = []; per_app = {}
for app, plan in G["plans"].items():
    for i, (f, t, r) in enumerate(plan):
        rid = f"{app}_r{i:03d}_{f}_{t}_{r}"; m = json.load(open(f"{D}/{rid}.json")); fe = G["features"](m)
        for s, v in fe["series"].items():
            have = {b for (b, rt, n) in v if b >= 3}; tot += G["NW"] - 3; miss += (G["NW"] - 3) - len(have)
            if s == G["FRONT"][app]: fmiss.append((G["NW"] - 3) - len(have))
out = dict(service_windows=tot, missing=miss, share=miss / tot, frontend_missing_windows_total=int(sum(fmiss)), services_per_run_median=None)
json.dump(out, open(f"{H}/../results/missingness_study2.json", "w"), indent=1); print(out)
