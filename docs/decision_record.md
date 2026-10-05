# Decision record 001 — How the lead flow retries CRM writes

**Status:** accepted (see `docs/code_review.md` for review outcome)
**Scope:** `app/crm_client.py` only

## Problem

`push_lead` retried every error 8 times with a fixed 0.5 s sleep and no idempotency key. Measured on the synthetic baseline: a timeout after the CRM saved the record created a duplicate contact; a permanent 400 cost 8 requests and 4.0 s before failing; the 200-lead batch produced 20 duplicates and 1.475 requests per lead.

## Decision

1. Retry only transient failures: timeouts and 5xx. Fail on the first attempt for any 4xx, **including 429** (changed in review, R1).
2. Cap at 3 attempts, exponential backoff 0.2 s → 0.4 s (0.6 s worst case).
3. Send one `Idempotency-Key` per submission, reused on every attempt. The key is a **required** argument, created per request in `main.py` (changed in review, R2).
4. Keep all of this in a frozen `RetryPolicy` dataclass injected into `CRMClient`.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Keep 8 attempts, just stop retrying 4xx | Fixes wasted calls on 400s but leaves duplicates and 4 s outages. |
| Use a library (`tenacity`, `backoff`) | Works, but adds a dependency for ~20 lines and hides the policy in decorators. Reasonable later if more clients need retries. |
| De-duplicate by email in our service (look up before create) | Extra read per lead (2 requests instead of 1), race condition between lookup and create, and blocks a legitimate re-submission from the same person. |
| Idempotency key = hash of email | Also blocks legitimate re-submissions (same person, new enquiry) for as long as the CRM keeps keys. A per-submission key only removes duplicates caused by our own retries, which is the defect. |
| Durable queue / outbox for failed leads | Right long-term answer for CRM outages, but a new component (storage, worker, monitoring). Out of scope for one focused change; listed as follow-up. |
| Jittered backoff | Matters with many concurrent clients hitting one API. Not measurable in this single-process test; easy to add in `delay_before_retry`. |

## Trade-offs accepted

- **Relies on the CRM honouring `Idempotency-Key`.** The fake does. A real CRM must be checked; if it doesn't, duplicates come back and the email-lookup alternative is needed.
- **Fewer attempts means some long outages now fail sooner** (3 attempts / 0.6 s instead of 8 / 4.0 s). Neither version survives a multi-second outage; only a queue would.
- **429 now fails immediately (R1).** In the synthetic `rate_limited_then_ok` scenario the baseline succeeded after one 0.5 s retry; the new code returns 502. Chosen because short retries against a real rate limit mostly burn quota, and the right handling (wait for `Retry-After`, or queue) is a separate change. This is a real regression for brief rate limits until a queue exists.
- **Callers must pass a key (R2).** Slightly more code at the call site; in exchange nobody can add a higher-level retry without seeing the key.
- **Permanent 4xx still returns HTTP 502** to the form. Unchanged behaviour; the user cannot tell their input was the problem. Tied to DEFECT-3 (validation), out of scope.
