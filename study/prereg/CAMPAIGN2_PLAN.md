# Campaign 2: gradual faults on two applications. Plan fixed before any campaign-2 run (2026-10-29)

## Why
Campaign 1 (results/VERDICT_2026-10-29.md) found no early warning, with only 15 cascades. 13 of them came from stall faults, which reach users within one window by construction. Campaign 2 asks the question where early warning is physically possible: faults that grow gradually. It adds a second application for generality, and a resource signal that may lead latency.

## Design (harness: crs-campaign repo, `campaign2.py`, `inject2.py`, `loadgen2.py`, `collect2.py`)
- **Applications:**
  - DeathStarBench socialNetwork: 16 targets, as in campaign 1.
  - DeathStarBench hotelReservation: 14 targets (9 services, 3 MongoDB, 2 Memcached; the frontend is excluded).
  - Both are from the same commit. Jaeger is pinned to 1.57, with sampling at 0.1.
- **Workload:** 100 req/s open-loop Poisson, each app's own DeathStarBench mixed workload.
- **Timeline per run (660 s):** 0–240 s normal; 240–540 s fault ramps in 30 steps of 10 s; 540–660 s recovery.
- **Faults:**
  - cpu_ramp_slow: CPU quota from 1.0 to 0.02 cores;
  - net_ramp: netem egress delay from 5 to 150 ms;
  - none.
- **Runs:** per app, targets × 2 faults × 2 repetitions, plus 12 none, in randomized order (seed 20261029 social, 20261030 hotel). That is 76 social and 68 hotel runs, 144 in all. They run on 20 GitHub runners (4 vCPU, 16 GB), with the same health gate as campaign 1 (including the queryable-frontend-traces check) and one retry on failure.
- **Resource sampling:** every container's cgroup cpu.stat every 5 s.

## Ground truth, detectors, thresholds, metrics
- **Same as SCORING_PLAN.md:**
  - 30-s windows;
  - SLO breach = p95 above max(5 × baseline, 100 ms) or errors above 5%;
  - cascade = a breach between fault start and fault end + 60 s;
  - M1–M6 unchanged;
  - τ = maximum over the first 4 none runs of each app (8 calibration runs in total), excluded from reporting.
- **New, pre-registered:**
  - **M7 resource signal:** per container, the robust z (paper's formula, cumulative history, min 3) of log1p(CPU throttled time in the window); run score = max over containers.
  - **M8 CRS + resource:** the naive CRS with max(z_throttle, 0) added inside the sum. Containers are matched to call-graph service names by compose service name.

## Hypotheses and decision rules (stated before the data)
- **H1:** On campaign-2 cascade runs, M1 alerts before onset (lead > 0) in more than half of them, and M1's lead exceeds M6's (paired one-sided Wilcoxon, p < 0.05).
- **H2:** M7 or M8 leads M6 on cpu_ramp_slow cascades (same test).
- **H3:** False alarms for M1 stay below 1 per hour of control time.
- **If H1 fails:** campaign 2 confirms campaign 1 on gradual faults and a second application. The paper then reports a robust negative result.

Smoke runs (shortened, 2 per app, commit c0280b2) test the plumbing only and are never scored.

Smoke 2 (commit ab60b32, 2026-11-01) validated the plumbing: clean CPU restore, netem rc=0, throttling sampled. No smoke run is scored. Full run launched as commit b27e59a at 22:22 UTC Nov 1. Fix before launch: CPU faults write cgroup cpu.max directly (docker update could not clear limits), and the health gate is p95 < 60 ms.
