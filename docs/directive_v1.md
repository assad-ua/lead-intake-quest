# Directive v1 — instructions given to the AI coding agent

Written before the fix, from `intent.md`. This is the version the agent worked from. The final version is `directive.md` in the repo root.

## Context

FastAPI service, one flow: `POST /leads` → score → `CRMClient.push_lead()` → CRM. CRM is faked in `app/fake_crm.py` (supports an `Idempotency-Key` header). Baseline numbers are in `results/baseline.json`. `DEFECT-1` in `app/crm_client.py` is the target.

## Task

Replace the retry loop in `CRMClient.push_lead` so that:

1. Only transient errors retry: `CRMTimeout`, HTTP 429, HTTP 5xx.
2. Permanent errors (other 4xx) fail on the first attempt.
3. At most 3 attempts total, exponential backoff (base 0.2 s, doubling), using the injected `sleep`.
4. Every attempt for one submission sends the same `Idempotency-Key`, so a retry after a lost response does not create a duplicate.
5. The retry settings live in one small named object with defaults, not in loop internals.

## Boundaries

- Touch only `app/crm_client.py`, `app/main.py` (only to pass the key), and new test files.
- Do not change `app/fake_crm.py`, `app/scoring.py`, `app/models.py`, or the measurement script.
- Do not fix DEFECT-2 or DEFECT-3.
- No new dependencies.
- Keep the public signature `CRMClient(transport, sleep=...)` and the API response shape.

## Acceptance criteria

- `pytest` passes, including the existing happy-path tests unchanged.
- New tests cover: duplicate prevention after `timeout_after_commit`; 400 fails in 1 request with no sleep; 500-forever stops at 3 requests; 429 then ok recovers; backoff delays are exactly `[0.2, 0.4]`.
- `python scripts/measure.py after` shows: 0 duplicates in the batch; 1 request for `crm_rejects_400`; ≤ 3 requests for `crm_down_500`.

## Review responsibilities

- Agent: implement, run tests and measurement, report what it changed and anything it was unsure about. Must not edit tests to make them pass.
- Human (Assad): review the diff line by line against the checklist in `docs/review_checklist.md`, reject or correct anything that is wrong, decide merge.
