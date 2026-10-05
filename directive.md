# directive.md — Final directive: reliable CRM writes in the lead-intake flow

> Repository: **[REPO_URL]** (private; reviewer access granted). All links below are relative to the repo root.
> Developed from [`intent.md`](intent.md). The version the agent first worked from is [`docs/directive_v1.md`](docs/directive_v1.md).

## 1. Objective

One website form submission must create **at most one** CRM contact, permanent CRM errors must fail fast, and transient errors must recover with a small, bounded number of attempts. The retry policy must be one named place another engineer can change and test.

## 2. Context

- Synthetic FastAPI service, one flow: `POST /leads` → score → `CRMClient.push_lead()` → CRM.
- CRM is an in-process fake ([`app/fake_crm.py`](app/fake_crm.py)) driven by outcome scripts; it honours `Idempotency-Key`.
- Three deliberate, labelled defects: `DEFECT-1` retries (target), `DEFECT-2` duplicated scoring, `DEFECT-3` no validation.
- Baseline: [`results/baseline.json`](results/baseline.json).

## 3. Quality yardstick

A change to this flow is acceptable when:

1. **No duplicate writes** caused by our own retries (lost response after the CRM saved).
2. **Bounded cost:** worst-case CRM requests and waiting per submission are fixed and computable from config.
3. **Right errors retried:** timeouts and 5xx only; 4xx (including 429) fail on attempt 1.
4. **One place to change:** retry behaviour lives only in `RetryPolicy`.
5. **Tests catch regressions:** new tests fail on the baseline code; sleeps are injected and asserted exactly.
6. **Evidence is reproducible:** one command regenerates before/after numbers.

## 4. Scope and boundaries

- In scope: `app/crm_client.py`; one line in `app/main.py` to create the key; tests.
- Out of scope (unchanged, still labelled): DEFECT-2, DEFECT-3, user double-submits, durable queue, circuit breaker, real CRM, async.
- No new dependencies. Constructor stays `CRMClient(transport, sleep=..., policy=...)`. API response shape unchanged.
- One process-level exception was made during handoff: `app/fake_crm.py` now accepts any numeric HTTP status (test-support only, commit `71f66a4`).

## 5. Requirements

1. `RetryPolicy` (frozen dataclass): `max_attempts=3`, `base_delay_s=0.2` doubling, `retry_statuses = 500–599`. Timeouts are always transient.
2. `push_lead(payload, idempotency_key)` — key **required**; same key on every attempt.
3. `main.py` creates one UUID key per request.
4. Final failure raises `CRMError` with the original exception as `__cause__`; API maps it to 502 (unchanged).

## 6. Completion criteria

- [x] `pytest` passes, existing happy-path tests unchanged.
- [x] New retry tests fail on baseline code.
- [x] Batch: 0 duplicates. `crm_rejects_400`: 1 request, 0 s wait. `crm_down_500`: 3 requests, 0.6 s.
- [x] Decision record, review record, handoff note committed.
- [ ] Human handoff run recorded (see Appendix A.6).

## 7. Roles and review

- **AI coding agent (Claude):** built the synthetic service and measurement script, drafted docs, implemented the fix, ran tests and measurements, flagged its own open questions.
- **Me (Ussama Assad):** chose the problem and scope, set the criteria, reviewed the agent's diff, decided both review findings (rejected one behaviour, required one correction), owns merge and the Loom.

---

# Appendix A — Results and handoff

## A.1 Artifacts

| Artifact | Link |
|---|---|
| Runnable repo | [REPO_URL] (also attached as `lead-intake-quest.zip`) |
| Focused diff: baseline → final | [`results/fix.diff`](results/fix.diff) (`app/crm_client.py`, `app/main.py`) |
| Review corrections diff | [`results/review_corrections.diff`](results/review_corrections.diff) |
| Code review example | [`docs/code_review.md`](docs/code_review.md) |
| Decision record | [`docs/decision_record.md`](docs/decision_record.md) |
| Review checklist | [`docs/review_checklist.md`](docs/review_checklist.md) |
| Handoff note + exercise | [`docs/handoff.md`](docs/handoff.md) |
| Tests | [`tests/`](tests/) — result in [`results/pytest_after.txt`](results/pytest_after.txt) |
| New tests vs baseline | [`results/new_tests_vs_baseline.txt`](results/new_tests_vs_baseline.txt) |
| Measurements | [`results/baseline.json`](results/baseline.json), [`results/after.json`](results/after.json), script [`scripts/measure.py`](scripts/measure.py) |

Commit history (`git log --oneline`) shows the order: baseline → intent + directive v1 → agent fix → fake CRM tweak → review docs → review corrections.

## A.2 Reproduce

```bash
pip install -r requirements.txt
python -m pytest -q                              # 15 passed
PYTHONPATH=. python scripts/measure.py after     # prints the table below

# Baseline numbers: check out the baseline commit
git checkout fa8883f -- app && PYTHONPATH=. python scripts/measure.py baseline && git checkout HEAD -- app
```

## A.3 Before / after — measured

All values **measured** on the synthetic fake CRM, single local run. Waiting time is simulated seconds recorded from the client's `sleep()` calls. Not a production measurement.

| Scenario | Baseline: HTTP / CRM requests / contacts / wait | After |
|---|---|---|
| healthy | 201 / 1 / 1 / 0.0 s | 201 / 1 / 1 / 0.0 s |
| timeout before save, then ok | 201 / 2 / 1 / 0.5 s | 201 / 2 / 1 / 0.2 s |
| **timeout after save, then ok** | 201 / 2 / **2 (duplicate)** / 0.5 s | 201 / 2 / **1** / 0.2 s |
| **429, then ok** | **201** / 2 / 1 / 0.5 s | **502** / 1 / 0 / 0.0 s ← deliberate trade-off (R1) |
| **CRM rejects 400** | 502 / **8** / 0 / **4.0 s** | 502 / **1** / 0 / **0.0 s** |
| CRM down (500 forever) | 502 / 8 / 0 / 4.0 s | 502 / 3 / 0 / 0.6 s |

**200-lead batch** (synthetic fault mix — rates are my assumption: 80% ok, 8% timeout after save, 5% timeout before save, 4% two 500s, 3% permanent 400):

| Metric | Baseline | After |
|---|---|---|
| Duplicate contacts | 20 | **0** |
| CRM requests per lead | 1.475 | **1.195** |
| Total simulated waiting | 51.5 s | **9.0 s** |
| Failed submissions | 8 | 8 (the 400s; unchanged) |

Unchanged on purpose (non-goals): scoring drift 16/24 inputs; invalid emails accepted 5/5.

**Estimates, not measured:** "steps to change the retry policy" — before: edit loop body, no tests to check it; after: 1 field in `RetryPolicy` + 1 test (shown in the agent's handoff demo, A.6). `wall_ms` in the JSON files is real time but noise at this scale; not used for claims.

## A.4 Checks

- `pytest`: **15 passed** ([`results/pytest_after.txt`](results/pytest_after.txt)).
- Agent's retry tests run against baseline code: **9 of 10 fail on behaviour**; the one passing is a guard expected to pass on both ([`results/new_tests_vs_baseline.txt`](results/new_tests_vs_baseline.txt)).

## A.5 AI contribution and corrections

- **AI (Claude) wrote:** the synthetic service and its deliberate defects, the measurement script, the fix in commit `e168641`, the tests, and first drafts of all docs including this one.
- **AI self-review flagged two risks** (R1, R2 in [`docs/code_review.md`](docs/code_review.md)). I read the diff and decided:
  - **R1 rejected:** the agent retried 429 with a 0.2/0.4 s backoff, ignoring `Retry-After`. Risk: against a real rate limit, quick retries burn quota and fail anyway, and the fake hid this because it returns 429 then ok. 429 now fails on attempt 1. Cost accepted: brief rate limits now return 502.
  - **R2 corrected:** the agent silently generated a key inside `push_lead`. Risk: a future queue that calls `push_lead` again would get a new key each time and bring duplicates back without warning. Key is now required and created per request.
- **Agent self-correction during handoff:** its first handoff attempt failed because the fake CRM only knew fixed status codes; fixed in `71f66a4`.

## A.6 Handoff

- Exercise and context: [`docs/handoff.md`](docs/handoff.md).
- **Limitation:** no second engineer has run it. The 408 part was demonstrated by the AI agent, not a human ([`results/handoff_demo.diff`](results/handoff_demo.diff)).
- Human run: [HANDOFF_RESULT — fill in: who ran it (me or another engineer), time taken, what was unclear. If only I ran it, say so.]

## A.7 Limitations

- Everything runs against a fake CRM. Whether a real CRM honours `Idempotency-Key` is untested and decides whether the duplicate fix holds.
- Fault rates in the batch are assumptions, not observed data. No team-wide or production impact is claimed.
- Leads that fail after all retries (outage, 429, 400) are lost with a 502. A queue/outbox is the follow-up.
- DEFECT-2 and DEFECT-3 remain.
- Actual effort: [EFFORT — fill in your real hours].
