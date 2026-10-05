# Handoff note — lead intake / CRM retries

## What you need to know (2 minutes)

- One flow: `POST /leads` (`app/main.py`) → `CRMClient.push_lead()` (`app/crm_client.py`) → CRM.
- The CRM is fake and in-process: `app/fake_crm.py`. You drive it with a list of outcomes, e.g. `FakeCRM(["timeout_after_commit", "ok"])` or any HTTP status as a string (`"408"`).
- **All retry behaviour lives in `RetryPolicy`** (attempts, backoff, which statuses retry). Change it there, nowhere else.
- Every attempt for one submission carries the same `Idempotency-Key`. Do not generate the key inside the retry loop.
- `DEFECT-2` (duplicated scoring in `main.py`) and `DEFECT-3` (no email validation) are known and deliberately left in place.

## Setup and checks

```bash
pip install -r requirements.txt
python -m pytest -q                          # expect: all passed
PYTHONPATH=. python scripts/measure.py mine  # writes results/mine.json
```

Compare `results/mine.json` with `results/after.json`. Only `wall_ms` should differ (it is real time and noisy).

## Handoff exercise (target: under 15 minutes)

> The CRM vendor says HTTP 408 (request timeout) is safe to retry, and asks you to allow 4 attempts.

1. In `app/crm_client.py`, change `RetryPolicy`: add `408` to `retry_statuses`, set `max_attempts = 4`.
2. Add a test in `tests/test_crm_retry.py`: `FakeCRM(["408", "ok"])` → 2 requests, success.
3. Update `test_crm_down_stops_after_max_attempts_with_backoff` to expect 4 requests and sleeps `[0.2, 0.4, 0.8]`.
4. Run `pytest` and `scripts/measure.py`. Check `crm_down_500` now shows 4 requests and 1.4 s wait.
5. Use `docs/review_checklist.md` before opening a PR.

**Expected size:** 1 source file, 1 test file. Before the fix, the same change meant editing the loop body in place, with no tests to catch a mistake.

## Handoff evidence — limitation

No second engineer has done this exercise yet. What exists:

- **Demonstrated by the AI agent (Claude), not a human:** the 408 part (steps 1–2) on a throwaway branch. First attempt failed: the fake CRM only accepted a fixed list of status codes, so step 2 needed an edit to the fake as well. Fixed in commit `71f66a4` (fake now accepts any numeric status). Second attempt: 1 source line + 1 test, 13 tests passed. The diff is in `results/handoff_demo.diff`.
- **Human run:** see the "Handoff" row in `directive.md` → Results appendix.
