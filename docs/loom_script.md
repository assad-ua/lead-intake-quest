# Loom script (≤ 5 min) — for Assad, not part of the submission

Say it in your own words. Screen: VS Code / terminal + this repo.

**0:00–0:45 — Problem and why first** (open `intent.md`, scoring table)
- Lead form → CRM. Three labelled defects. Scored on user impact, operating cost, maintenance.
- Retries won: only one that creates bad data (duplicates) and multiplies calls to a rate-limited API. Baseline: 20 duplicates in 200 synthetic leads, 8 requests and 4 s on a permanent 400.

**0:45–2:00 — Demo** (terminal)
- `python -m pytest -q` → 15 passed.
- `PYTHONPATH=. python scripts/measure.py after` → walk the table: duplicate gone, 400 = 1 request, 500 = 3 requests.
- Open `results/fix.diff`: `RetryPolicy`, same key on every attempt.

**2:00–3:15 — Verification and the revision** (open `docs/code_review.md`)
- Tests fail on baseline (9 of 10) — show `results/new_tests_vs_baseline.txt`.
- R1: agent retried 429 with tiny backoff. Rejected it — explain why, and say the cost: a short rate limit now returns 502.
- R2: key was silently generated. Made it required.
- Be clear: the agent flagged both; the decisions were yours.

**3:15–4:15 — AI use**
- Claude built the synthetic service, wrote the fix, tests, and drafted docs. You set problem, criteria, scope, and made the review calls.
- Handoff demo was run by the agent and found a real gap in the fake CRM.

**4:15–5:00 — Limitations**
- Fake CRM; real CRM must honour Idempotency-Key. Fault rates assumed. Failed leads still lost — next step is a queue. DEFECT-2 and 3 left on purpose.
