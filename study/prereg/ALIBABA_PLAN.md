# Alibaba re-analysis: plan fixed before the run (2026-10-28)

## 1. Reproduction
- Re-pull windows 0–499 of MCRRTUpdate and CallGraph with the paper's own aggregation logic:
  - MCR: per-service mean of max(providerrpc_rt, consumerrpc_rt), and mean of providerrpc_mcr + consumerrpc_mcr.
  - CallGraph: um→dm call counts, excluding UNKNOWN/USER callers.
- Run `run_pipeline_v3.py` and `run_evaluation_v3b.py` unchanged.
- Expected (August run): 8 events, 31 positive rows, AUC 0.8267 fitted / 0.8360 naive / 0.7944 latency / 0.5558 static. Any difference is reported.

## 2. Circularity, stated
The labels come from latency z-scores above 3 on the upstream service and on at least 3 of its callees, in window w or w+1. The latency-z feature is therefore partly the label itself. The August AUCs measure agreement with that heuristic, not prediction.

## 3. Forward (early-warning) evaluation
- **Target:** for each row (s, w) that is not itself labelled, whether s is labelled in any of windows w+1, w+2 or w+3.
- **Exclusion:** rows already labelled at w are dropped, so the score must warn before the event.
- **Scores:**
  - naive Cascade Risk Score;
  - latency z;
  - call-rate z;
  - blast radius;
  - sliding-window latency z (previous 10 windows);
  - static global threshold.
- **Reported:** AUC-ROC and AUC-PR for each score, with the number of positives.
- **Event level:** for each event, the first window up to 3 windows ahead in which the upstream service's naive score is in the top 0.1% of all rows.
- **No fitting:** the fitted logistic model is not used here, because in-sample fitting on the evaluation labels cannot measure early warning.
