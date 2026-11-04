"""Figures for the EMSE paper, computed from the Study-2 run data with the same code as score2.py.
Usage: python3 figures.py RUNDIR OUTDIR
Fig. 1: one net_ramp cascade - frontend p95 (top) and the CRS / end-to-end scores against their thresholds (bottom).
Fig. 2: lead time before the SLO breach, per method, over the 57 Study-2 cascades.
"""
import sys, os, json, math
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
RUNDIR, OUTDIR = sys.argv[1], sys.argv[2]; os.makedirs(OUTDIR, exist_ok=True)
H = os.path.dirname(os.path.abspath(__file__))
src = open(f"{H}/score2.py").read().split("runs = []; calib = set()")[0]
sys.argv = ["score2.py", RUNDIR, "/dev/null"]; exec(compile(src, "score2.py", "exec"))
S = json.load(open(f"{H}/results/score2_campaign2.json"))
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, MUTED, GRID = "#0b0b0b", "#6b6a64", "#e4e3de"
plt.rcParams.update({"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "font.family": "serif"})

# ---- Fig. 1: pick the social net_ramp cascade whose breach comes late in the ramp (onset bin >= 13) and that both detectors flag before the breach, first in plan order
casc = [k for k in S["truth"] if S["truth"][k]["cascade"] and k not in S["calibration"] and "_none_" not in k]
tau1, tau6 = S["methods"]["M1"]["tau"], S["methods"]["M6"]["tau"]
pick = None
for rid in sorted(casc):
    if not rid.startswith("social") or "net_ramp" not in rid: continue
    meta = json.load(open(f"{RUNDIR}/{rid}.json")); f = features(meta); t = S["truth"][rid]
    s1 = window_scores(f, "M1"); s6 = window_scores(f, "M6")
    a1 = [b for b, v in sorted(s1.items()) if v > tau1 and b >= F0 // W]; a6 = [b for b, v in sorted(s6.items()) if v > tau6 and b >= F0 // W]
    if a1 and a6 and t["onset_bin"] >= 13 and a1[0] < t["onset_bin"] and a6[0] < t["onset_bin"]: pick = (rid, meta, s1, s6, t, a1[0], a6[0]); break
rid, meta, s1, s6, t, b1, b6 = pick
r = pd.read_csv(f"{RUNDIR}/{rid}.req.csv"); r["b"] = ((r.t - meta["t0"]) // W).astype(int); r = r[(r.b >= 0) & (r.b < NW)]
p95 = r.groupby("b").lat_ms.quantile(.95)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.45, 3.3), sharex=True, gridspec_kw=dict(height_ratios=[1.1, 1], hspace=0.12))
x = (p95.index + 0.5) * W
ax1.plot(x, p95.values, color=INK, lw=1.6); ax1.axhline(t["slo"], color=MUTED, lw=1, ls="--")
ax1.text(10, t["slo"] * 1.08, f"SLO {t['slo']:.0f} ms", color=MUTED, fontsize=7)
ax1.set_ylabel("frontend p95 (ms)"); ax1.set_yscale("log")
for ax in (ax1, ax2):
    ax.axvspan(F0, F1, color=GRID, alpha=0.6, lw=0); ax.axvline(t["onset_bin"] * W, color=INK, lw=0.8)
    ax.grid(axis="y", color=GRID, lw=0.6)
ax1.text(F0 + 5, 12, "fault ramp", color=MUTED, fontsize=7)
ax1.text(t["onset_bin"] * W + 5, ax1.get_ylim()[0] * 1.3, "breach", color=INK, fontsize=7)
bs = [b for b in sorted(s1) if s1[b] > 0]; y1 = [s1[b] / tau1 for b in bs]; bs6 = [b for b in sorted(s6) if s6[b] > 0]; y6 = [s6[b] / tau6 for b in bs6]
ax2.plot([(b + 0.5) * W for b in bs], y1, color=BLUE, lw=2, marker="o", ms=3); ax2.plot([(b + 0.5) * W for b in bs6], y6, color=ORANGE, lw=2, marker="s", ms=3)
ax2.axhline(1, color=MUTED, lw=1, ls="--"); ax2.set_yscale("log"); ax2.set_ylabel("score / threshold")
from matplotlib.ticker import FixedLocator, FixedFormatter
ax2.yaxis.set_major_locator(FixedLocator([0.5, 1, 2, 5])); ax2.yaxis.set_major_formatter(FixedFormatter(["0.5", "1", "2", "5"])); ax2.yaxis.set_minor_locator(FixedLocator([]))
ax2.text(5, 1.12, "alert threshold", color=MUTED, fontsize=7)
ax2.text((bs[-1] + 0.7) * W, y1[-1], "CRS", color=BLUE, fontsize=7, va="center", fontweight="bold"); ax2.text((bs6[-1] + 0.7) * W, y6[-1] * 1.6, "end-to-end", color=ORANGE, fontsize=7, va="center", fontweight="bold")
ax2.annotate("", xy=((b1 + 0.5) * W, 1), xytext=((b1 + 0.5) * W, 0.55), arrowprops=dict(arrowstyle="->", color=BLUE, lw=1))
ax2.annotate("", xy=((b6 + 0.5) * W, 1), xytext=((b6 + 0.5) * W, 0.55), arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1))
ax2.set_xlabel("time in run (s)"); ax2.set_xlim(0, NW * W + 70)
fig.savefig(f"{OUTDIR}/fig_timeline.pdf", bbox_inches="tight"); plt.close(fig)
json.dump(dict(run=rid, onset_s=t["onset_bin"] * W, crs_alert_s=b1 * W, e2e_alert_s=b6 * W, slo_ms=t["slo"]), open(f"{OUTDIR}/fig_timeline.json", "w"), indent=1)

# ---- Fig. 2: lead-time distributions (dot strip, jittered; median bar)
meth = [("M6", "end-to-end", ORANGE), ("M1", "CRS", BLUE), ("M2", "latency z", AQUA), ("M5", "sliding z", YELLOW), ("M8", "CRS+throttle", MAGENTA)]
fig, ax = plt.subplots(figsize=(3.45, 2.2)); rng = np.random.default_rng(0)
for i, (m, lab, c) in enumerate(meth):
    L = np.array(S["methods"][m]["lead_s"]); y = i + rng.uniform(-0.18, 0.18, len(L))
    ax.scatter(L + rng.uniform(-4, 4, len(L)), y, s=9, color=c, edgecolor="white", linewidth=0.4, zorder=3)
    med = np.median(L); ax.plot([med, med], [i - 0.32, i + 0.32], color=INK, lw=1.6, zorder=4)
    ax.text(305, i, f"{lab}  (median {med:.0f} s)", va="center", fontsize=7, color=INK)
ax.set_yticks([]); ax.axvline(0, color=MUTED, lw=0.8); ax.set_xlim(-20, 300); ax.set_xlabel("warning before SLO breach (s)")
ax.grid(axis="x", color=GRID, lw=0.6); ax.spines["left"].set_visible(False)
fig.savefig(f"{OUTDIR}/fig_leads.pdf", bbox_inches="tight"); plt.close(fig)
print("figures written; timeline run", rid)
