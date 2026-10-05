# Code review — commit `e168641` (agent output, DEFECT-1 fix)

Reviewer: Ussama Assad. Author of the change: AI coding agent (Claude), working from `docs/directive_v1.md`.

Checklist used: `docs/review_checklist.md`.

## Checklist result

| Item | Result |
|---|---|
| Only timeouts / 429 / 5xx retry | Pass — `RetryPolicy.is_transient` |
| Hard cap, computable worst-case wait | Pass — 3 attempts, 0.6 s |
| Same key on every attempt | Pass — key built before the loop; `test_same_key_on_every_attempt` |
| Key unique per submission | Pass — `test_separate_submissions_get_separate_keys` |
| No bare `except Exception`, cause kept | Pass — catches `CRMTimeout`, `CRMHTTPError`; `raise ... from exc` |
| Sleep injected, delays asserted exactly | Pass |
| Tests fail on old code | Pass — 9 of 10 fail on baseline (`results/new_tests_vs_baseline.txt`). The one that passes on both is a guard against over-deduplication, expected. |
| Scope | Pass — only `app/crm_client.py` + new test file |
| Numbers re-run | Pass — `results/after.json` |

## Findings flagged by the agent for a human decision

**R1 — 429 is retried with a 0.2 s / 0.4 s backoff and ignores `Retry-After`.**
Risk: real CRM rate limits usually reset over seconds. Three quick retries likely all hit the limit again, burn quota, and fail anyway. The fake CRM returns 429 then ok, so the tests pass and hide this.

**R2 — `push_lead` silently generates the idempotency key when the caller passes none.**
Risk: if someone later adds a retry at a higher level (a queue worker calling `push_lead` again), each call gets a new key and duplicates come back with no warning. Making the key required would force the caller to think about it.

## Reviewer decision

Both findings were raised by the agent in its self-review. The decisions below are mine (Assad), made after reading `results/fix.diff`.

**R1 — rejected the agent's 429 handling.** 429 removed from `retry_statuses`; a rate-limited write now fails on the first attempt. I did not take the alternative of reading `Retry-After`: it needs the transport to expose headers, new fake behaviour and more tests, and waiting several seconds inside a form request is the wrong place anyway. Accepted cost: a short rate limit now returns 502 where the baseline happened to succeed (see `results/after.json`, `rate_limited_then_ok`). Follow-up: queue/outbox.

**R2 — corrected.** `idempotency_key` is now a required argument; `main.py` creates one UUID per request. Tests added: `test_key_is_required`, `test_api_sends_a_different_key_per_submission`.

Result after corrections: 15 tests pass; re-measured into `results/after.json`. Commit: see `git log` ("Review corrections").
