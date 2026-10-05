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

<!-- ASSAD: fill this in yourself after reading the diff. Record what you actually decided. -->
