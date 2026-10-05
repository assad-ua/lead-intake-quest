# Review checklist — CRM push / retry changes

Use for any change to `app/crm_client.py` or how `main.py` calls it.

- [ ] **Which errors retry?** Only timeouts, 429 and 5xx. A 4xx (other than 429) must fail on the first attempt.
- [ ] **Is there a hard cap?** Attempts are bounded. Worst-case total wait is easy to compute from the policy.
- [ ] **Same key on every attempt?** The `Idempotency-Key` is created once per submission, outside the retry loop, and reused.
- [ ] **Is the key unique per submission?** Not reused across different leads or requests.
- [ ] **Errors are not swallowed.** No bare `except Exception`. The final error carries the cause.
- [ ] **Sleep is injected.** Tests do not really sleep; delays are asserted exactly.
- [ ] **Tests fail on the old code.** New tests would catch a regression to the baseline (check with `git stash` / checkout).
- [ ] **Scope.** No changes to scoring, validation, fake CRM, or measurement script.
- [ ] **Numbers re-run.** `python scripts/measure.py after` re-run and `results/after.json` committed.
