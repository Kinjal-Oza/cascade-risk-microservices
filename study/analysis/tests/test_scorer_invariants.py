"""Invariant tests for the Study-2 scorer (score2.py), added for the EMSE revision.
Run: python3 -m pytest -q tests/   (from the study root; score2.py and method_src/ alongside)
Optional: CRS_RUNDIR=<Study-2 run dir> also checks the published numbers against a fresh scoring.
"""
import os, sys, json, gzip, math, tempfile, importlib.util
import numpy as np, pandas as pd, pytest

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{H}/method_src"); sys.path.insert(0, os.path.join(H, "..", "..", "src"))
import temporal_features_fast as TF, temporal_features as TF0, cascade_score as CS

def load_scorer(rundir):
    src = open(f"{H}/score2.py").read().split("runs = []; calib = set()")[0]
    G = {"__file__": f"{H}/score2.py", "__name__": "score2"}
    argv = sys.argv; sys.argv = ["score2.py", rundir, "/dev/null"]
    try: exec(compile(src, "score2.py", "exec"), G)
    finally: sys.argv = argv
    return G

def synth_run(d, rid, app="social", lat=lambda t: 8.0, err=lambda t: 0.0, svc_rt=None, seed=0):
    """Write a synthetic run: 100 req/s request log and a 3-service call graph (frontend -> a -> b)."""
    rng = np.random.default_rng(seed); t0 = 1_000_000.0; END = 660
    ts = np.sort(rng.uniform(0, END, 100 * END))
    lat_ms = np.array([lat(t) for t in ts]) * rng.uniform(0.8, 1.2, len(ts))
    status = np.where(rng.uniform(size=len(ts)) < np.array([err(t) for t in ts]), 500, 200)
    pd.DataFrame(dict(t=t0 + ts, lat_ms=lat_ms, status=status)).to_csv(f"{d}/{rid}.req.csv", index=False)
    fr = {"social": "nginx-web-server", "hotel": "frontend"}[app]
    svc_rt = svc_rt or {}
    rows = []
    for t in ts[::10]:
        for um, dm in (("USER", fr), (fr, "svc-a"), ("svc-a", "svc-b")):
            base = svc_rt.get(dm, lambda t: 2.0)(t)
            rows.append((int((t0 + t) * 1000), um, dm, base * rng.uniform(0.8, 1.2)))
    with gzip.open(f"{d}/{rid}.cg.csv.gz", "wt") as f:
        pd.DataFrame(rows, columns=["timestamp", "um", "dm", "rt"]).to_csv(f, index=False)
    meta = dict(run=rid, app=app, fault="net_ramp", target="svc-b", t0=t0)
    json.dump(meta, open(f"{d}/{rid}.json", "w")); return meta

@pytest.fixture(scope="module")
def env():
    d = tempfile.mkdtemp(); return d, load_scorer(d)

# ---- robust z ---------------------------------------------------------------------------------
def test_fast_z_equals_reference():
    rng = np.random.default_rng(1); s = [(i, float(rng.lognormal(2, .5)), float(rng.poisson(50))) for i in range(40)]
    a, b = TF.latency_deviation_score(s), TF0.latency_deviation_score(s)
    assert a.keys() == b.keys() and all(abs(a[k] - b[k]) < 1e-9 for k in a)

def test_z_is_causal():
    """No look-ahead: appending future windows never changes an earlier score."""
    rng = np.random.default_rng(2); s = [(i, float(rng.lognormal(2, .5)), 1.0) for i in range(30)]
    full, part = TF.latency_deviation_score(s), TF.latency_deviation_score(s[:15])
    assert all(full[k] == part[k] for k in part)

def test_z_minimum_history():
    s = [(i, 5.0, 1.0) for i in range(10)]
    assert min(TF.latency_deviation_score(s)) == 3   # first score after 3 windows of history

def test_crs_monotone_and_bounded():
    vals = [CS.naive_combined_score(b, l, c) for b in (0, 10, 1e4) for l in (-2, 0, 2) for c in (-1, 0, 3)]
    assert all(0 < v < 1 for v in vals)
    assert CS.naive_combined_score(0, 2, 0) > CS.naive_combined_score(0, 1, 0)
    assert CS.naive_combined_score(0, -5, -5) == CS.naive_combined_score(0, 0, 0)   # negative z clipped

# ---- ground truth ------------------------------------------------------------------------------
def test_no_fault_no_breach(env):
    d, G = env; m = synth_run(d, "t_quiet"); t = G["truth"](m)
    assert not t["cascade"] and t["slo"] == 100.0       # floor dominates a ~8 ms baseline

def test_latency_breach_onset(env):
    d, G = env; m = synth_run(d, "t_lat", lat=lambda t: 400.0 if t >= 330 else 8.0); t = G["truth"](m)
    assert t["cascade"] and t["onset_bin"] == 11

def test_error_only_breach(env):
    d, G = env; m = synth_run(d, "t_err", err=lambda t: 0.2 if t >= 300 else 0.0); t = G["truth"](m)
    assert t["cascade"] and t["onset_bin"] == 10

def test_breach_before_fault_is_not_a_cascade(env):
    d, G = env; m = synth_run(d, "t_pre", lat=lambda t: 400.0 if 60 <= t < 120 else 8.0); t = G["truth"](m)
    assert not t["cascade"] and t["pre_breach"] == [2, 3]

def test_breach_after_window_is_not_a_cascade(env):
    d, G = env; m = synth_run(d, "t_late", lat=lambda t: 400.0 if t >= 600 else 8.0); t = G["truth"](m)
    assert not t["cascade"]

# ---- detectors ---------------------------------------------------------------------------------
def test_frontend_detector_ignores_internal_services(env):
    d, G = env
    a = G["features"](synth_run(d, "t_m6a", seed=3))
    b = G["features"](synth_run(d, "t_m6b", seed=3, svc_rt={"svc-b": lambda t: 50.0 if t > 300 else 2.0}))
    assert G["window_scores"](a, "M6") == G["window_scores"](b, "M6")
    assert G["window_scores"](a, "M2") != G["window_scores"](b, "M2")

def test_internal_fault_raises_per_service_score(env):
    d, G = env
    f = G["features"](synth_run(d, "t_int", seed=4, svc_rt={"svc-b": lambda t: 60.0 if t > 300 else 2.0}))
    s = G["window_scores"](f, "M2"); assert max(v for b, v in s.items() if b >= 11) > max(v for b, v in s.items() if 3 <= b < 10)

def test_detectors_use_only_past_windows(env):
    """Truncating a run after window k leaves every score at windows <= k unchanged."""
    d, G = env; m = synth_run(d, "t_trunc", seed=5, svc_rt={"svc-b": lambda t: 40.0 if t > 400 else 2.0})
    c = pd.read_csv(f"{d}/t_trunc.cg.csv.gz"); k = 12
    with gzip.open(f"{d}/t_trunc2.cg.csv.gz", "wt") as fh:
        c[(c.timestamp / 1000 - m["t0"]) < (k + 1) * 30].to_csv(fh, index=False)
    m2 = dict(m, run="t_trunc2"); json.dump(m2, open(f"{d}/t_trunc2.json", "w"))
    for M in ("M1", "M2", "M5", "M6"):
        a, b = G["window_scores"](G["features"](m), M), G["window_scores"](G["features"](m2), M)
        assert all(abs(a[x] - b[x]) < 1e-12 for x in b if x <= k), M

# ---- published results -------------------------------------------------------------------------
def test_published_results_consistent():
    S = json.load(open(f"{H}/../results/score2_campaign2.json"))
    cal = set(S["calibration"]); assert len(cal) == 8
    assert all(not S["truth"][r]["cascade"] for r in cal)                      # calibration runs are no-fault
    assert all("_none_" in r for r in cal)
    for M in ("M1", "M2", "M5", "M6", "M8"):
        m = S["methods"][M]; assert m["detected"] == len(m["lead_s"]) and all(x % 30 == 0 for x in m["lead_s"])
    ev = [r for r in S["truth"] if r not in cal and S["truth"][r]["cascade"]]
    assert len(ev) == S["methods"]["M1"]["cascades"] == 57

def test_reanalysis_reproduces_preregistered():
    S = json.load(open(f"{H}/../results/score2_campaign2.json")); R = json.load(open(f"{H}/../results/reanalysis_study2.json"))
    for M in ("M1", "M2", "M5", "M6", "M8"):
        assert R["prereg_check"][M]["median_lead"] == S["methods"][M]["median_lead_s"]
        assert abs(R["prereg_check"][M]["fa_windows_h"] - S["methods"][M]["fa_per_hour"]) < 0.01
        assert R["prereg_check"][M]["detected"] == S["methods"][M]["detected"]

@pytest.mark.skipif(not os.environ.get("CRS_RUNDIR"), reason="set CRS_RUNDIR to the Study-2 run directory")
def test_rescoring_matches_published(tmp_path):
    import subprocess
    out = tmp_path / "s.json"; subprocess.run([sys.executable, f"{H}/score2.py", os.environ["CRS_RUNDIR"], str(out)], check=True, capture_output=True)
    a, b = json.load(open(out)), json.load(open(f"{H}/../results/score2_campaign2.json"))
    for M in a["methods"]: assert a["methods"][M]["lead_s"] == b["methods"][M]["lead_s"] and a["methods"][M]["false_alarms"] == b["methods"][M]["false_alarms"]
