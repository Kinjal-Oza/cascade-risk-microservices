# Practitioner survey: how much early warning is worth having?

Anonymous, about 5 minutes, 12 questions. Host it on Google Forms or Microsoft Forms with "collect email addresses" **off** and no sign-in required.

**Distribution:** the author's LinkedIn network, SRE and DevOps communities (r/sre, the SREcon Slack, CNCF Slack #sre), and personal contacts. Run it for two weeks. The target is at least 20 complete responses.

## Consent text (shown first)
> This short survey is part of an independent research study on alerting in microservice systems by Kinjal Vaishnav. It is anonymous: we do not collect names, email addresses or employers, and no question asks for confidential information about your organization. Taking part is voluntary; you can stop at any time, and partial answers are discarded. Aggregate results will be published in a research paper and in a public data file. By continuing you confirm you are 18 or older and agree to take part.
> [ ] I agree to take part

## Questions
**About you**
1. Which best describes your role? Single choice: SRE / Platform or infrastructure engineer / Software engineer who is on call / Engineering manager / Other.
2. Years of on-call experience. Single choice: <1 / 1–3 / 3–5 / 5–10 / >10.
3. Roughly how many services does the system you are on call for have? Single choice: <10 / 10–50 / 50–200 / 200–1000 / >1000 / Don't know.

**What you alert on today**
4. Which signals page you today? Select all that apply:
   - user-facing latency or error SLO, burn-rate style;
   - user-facing latency or error threshold, not burn-rate;
   - per-service latency or error thresholds;
   - per-service anomaly detection (baselines, ML);
   - resource signals (CPU, memory, saturation);
   - queue depth or consumer lag;
   - synthetic probes;
   - other.
5. Which of these has most often paged you **before** users were affected? Single choice from the same list, plus "none of them".

**What warning is worth**
6. Suppose a page arrives some time before an SLO would be breached. What is the smallest head start that would let you or your team do something useful: start mitigation, roll back, shed load, or fail over? Single choice: any head start is useful / 15 s / 30 s / 1 min / 2 min / 5 min / 15 min / more than 15 min.
7. Below what head start is an early page no more useful than the SLO page itself? Same choices as question 6.
8. How many false or non-actionable pages per on-call week are acceptable, in exchange for pages that come earlier? Single choice: 0 / 1 / 2–3 / 4–10 / more than 10.
9. For a typical incident, how long from the first page to the start of mitigation? Single choice: <1 min / 1–5 min / 5–15 min / 15–60 min / >1 h.

**Asynchronous paths**
10. Does your system have user-visible work that goes through queues or asynchronous jobs, such as feeds, notifications or order processing? Single choice: Yes / No / Don't know.
11. If yes: how do you detect when that work is delayed? Select all that apply:
    - queue depth or lag alerts;
    - end-to-end freshness or synthetic probes;
    - per-service latency;
    - user reports;
    - we don't;
    - other.
12. Optional free text: anything else about early warning you would like researchers to know. *(Please do not include names or confidential details.)*

## Analysis (fixed before data)
- **Descriptive only:** counts and shares per answer, by role and by experience.
- **Main figure:** the distribution of answers to questions 6 and 7. The paper compares these with the lead-time differences we observed (Studies 1–3).
- **Not used to change anything:** the survey does not change the Study 3 equivalence margin (±15 s), which was fixed before the survey.
- **Data release:** responses are published as a CSV. Free-text answers are reviewed and redacted before release.

## Ethics statement for the paper
> The survey was anonymous, collected no personal or organizational identifiers, and asked only about professional practice. Respondents gave informed consent before starting. The author is an independent researcher without access to an institutional review board; the study design follows the ACM SIGSOFT Empirical Standards for questionnaire surveys.
