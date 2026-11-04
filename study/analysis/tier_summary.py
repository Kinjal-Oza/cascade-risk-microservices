"""EXPLORATORY: Study 2 results by target tier (cache / database / logic service). From results/reanalysis_study2.json."""
import json, collections, numpy as np
o = json.load(open("../results/reanalysis_study2.json")); out = {}
tier = lambda t: "cache" if ("memcached" in t or "redis" in t) else "database" if "mongo" in t else "service"
agg = collections.defaultdict(lambda: dict(runs=0, cascades=0, m1=[], m6=[]))
for k, v in o["per_target"].items():
    app, fault, tgt = k.split("|"); a = agg[f"{app}|{fault}|{tier(tgt)}"]
    a["runs"] += v["runs"]; a["cascades"] += v["cascades"]; a["m1"] += v["m1"]; a["m6"] += v["m6"]
for k, a in sorted(agg.items()):
    out[k] = dict(runs=a["runs"], cascades=a["cascades"], median_lead_crs=float(np.median(a["m1"])) if a["m1"] else None,
                  median_lead_frontend=float(np.median(a["m6"])) if a["m6"] else None, ties=sum(x == y for x, y in zip(a["m1"], a["m6"])))
json.dump(out, open("../results/tier_summary_study2.json", "w"), indent=1)
for k, v in out.items(): print(k, v)
