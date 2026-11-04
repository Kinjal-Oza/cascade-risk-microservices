"""EXPLORATORY (not pre-registered): does the highest-scoring service during the fault window name the injected target?"""
import sys, json, collections, numpy as np
sys.argv = [sys.argv[0], sys.argv[1], "/dev/null"]
exec(open("score_testbed.py").read().split("runs = []")[0])
STORE = {"home-timeline-redis": "home-timeline-service-redis", "user-timeline-mongodb": "user-timeline-service-mongo",
         "post-storage-mongodb": "post-storage-service-mongo", "post-storage-memcached": "post-storage-service-memcached",
         "social-graph-mongodb": "social-graph-service-mongo"}
res = collections.defaultdict(lambda: collections.Counter())
for i, (fault, tgt, rep) in enumerate(plan):
    if fault in ("none", "surge"): continue
    rid = f"r{i:03d}_{fault}_{tgt}_{rep}"; meta = json.load(open(f"{D}/{rid}.json")); f = features(meta); t = truth(meta)
    tg = STORE.get(tgt, tgt)
    for M in ("M1", "M2", "M5"):
        best = {}
        for s in f["series"]:
            for b in range(F0 // W, F1 // W):
                l = f["lz"][s].get(b); c = f["cz"][s].get(b)
                if M == "M1" and l is not None and c is not None: v = CS.naive_combined_score(f["blast"].get(s, 0.0), l, c)
                elif M == "M2" and l is not None: v = l
                elif M == "M5" and f["sz"][s].get(b) is not None: v = f["sz"][s][b]
                else: continue
                best[s] = max(best.get(s, -1e9), v)
        rank = sorted(best, key=best.get, reverse=True)
        k = "cascade" if t["cascade"] else "local"
        res[(M, k)]["n"] += 1; res[(M, k)]["top1"] += int(rank[:1] == [tg]); res[(M, k)]["top3"] += int(tg in rank[:3])
        res[(M, k, fault)]["n"] += 1; res[(M, k, fault)]["top1"] += int(rank[:1] == [tg])
for k in sorted(res, key=str): print(k, dict(res[k]))
