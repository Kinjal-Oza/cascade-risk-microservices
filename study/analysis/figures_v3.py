"""Revision figures, from results/reanalysis_study2.json (no run data needed).
Fig. 2 fig_paired.pdf : paired lead differences (detector minus end-to-end), Study 2, with cluster-bootstrap mean CI.
Fig. 3 fig_budget.pdf : cascades warned before the breach vs false-alarm incidents per control hour, thresholds from
                        calibration-score quantiles (0.90 ... 1.0), Study 2.
Usage: python3 figures_v3.py OUTDIR"""
import sys, os, json, collections
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(f"{H}/../results/reanalysis_study2.json"))
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, MUTED, GRID = "#0b0b0b", "#6b6a64", "#e4e3de"
plt.rcParams.update({"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "font.family": "serif"})

# ---- Fig. 2: paired differences
rows = [("M1-M6", "CRS", BLUE), ("M1int-M6", "CRS, internal only", BLUE), ("M2-M6", "latency z", AQUA),
        ("M5-M6", "sliding z", YELLOW), ("M8-M6", "CRS + throttling", MAGENTA)]
fig, ax = plt.subplots(figsize=(3.45, 2.3))
for i, (k, lab, c) in enumerate(rows):
    p = R["paired"][k]; y = len(rows) - 1 - i; cnt = collections.Counter(p["diffs"])
    for v, n in cnt.items():
        if v == 0: continue
        for j in range(n): ax.scatter(v, y + 0.13 + 0.13 * j, s=14, color=c, edgecolor="white", linewidth=0.5, zorder=3)
    lo, hi = p["mean_ci"]; ax.plot([lo, hi], [y - 0.12, y - 0.12], color=INK, lw=1.4, zorder=4)
    ax.scatter(p["mean"], y - 0.12, s=12, color=INK, zorder=5, marker="|")
    ax.text(335, y, f"{p['ties']} ties / {p['n']}", va="center", ha="right", fontsize=7, color=MUTED)
ax.axvline(0, color=MUTED, lw=0.8); ax.spines["left"].set_visible(False)
ax.set_yticks([len(rows) - 1 - i for i in range(len(rows))]); ax.set_yticklabels([r[1] for r in rows], fontsize=7, color=INK); ax.tick_params(axis="y", length=0)
ax.set_xlim(-295, 340); ax.set_ylim(-0.5, len(rows) - 0.3); ax.grid(axis="x", color=GRID, lw=0.6)
ax.set_xticks([-180, -90, 0, 90, 180])
ax.set_xlabel("lead difference vs. end-to-end (s)\n< 0: end-to-end earlier     > 0: detector earlier", fontsize=7)
fig.savefig(f"{OUT}/fig_paired.pdf", bbox_inches="tight"); plt.close(fig)

# ---- Fig. 3: alarm budget
meth = [("M6", "end-to-end", ORANGE, "s"), ("M1", "CRS", BLUE, "o"), ("M2", "latency z", AQUA, "^"), ("M5", "sliding z", YELLOW, "D")]
fig, ax = plt.subplots(figsize=(3.45, 2.3))
for m, lab, c, mk in meth:
    pts = sorted((r["fa_incidents_h"], r["early"]) for r in R["budget"][m])
    x = [max(a, 0.05) for a, b in pts]; y = [b for a, b in pts]
    ax.plot(x, y, color=c, lw=2, marker=mk, ms=4, markeredgecolor="white", markeredgewidth=0.5, zorder=3)
    pre = R["prereg_check"][m]; ax.scatter(max(pre["fa_incidents_h"], 0.05), pre["early"], s=40, facecolor="none", edgecolor=INK, lw=0.8, zorder=4)
    ax.lines[-1].set_label(lab)
ax.legend(loc="upper left", fontsize=7, frameon=False)
ax.set_xscale("log"); ax.set_xlim(0.06, 30); ax.set_ylim(46.5, 56.5)
ax.set_xticks([0.1, 0.3, 1, 3, 10]); ax.set_xticklabels(["0.1", "0.3", "1", "3", "10"])
ax.set_xlabel("false-alarm incidents per control hour"); ax.set_ylabel("cascades warned before breach (of 57)")
ax.grid(color=GRID, lw=0.6)
ax.text(0.065, 47.0, "open circles: pre-registered threshold", fontsize=6.5, color=MUTED)
fig.savefig(f"{OUT}/fig_budget.pdf", bbox_inches="tight"); plt.close(fig)
print("written")
