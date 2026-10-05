# intent.md — Why this problem?

## Context

`lead-intake-quest` is a small synthetic FastAPI service I built for this Quest. It has one user-facing flow: a website form posts a lead to `POST /leads`, the service scores it, and pushes it to a CRM. The CRM is an in-process fake (`app/fake_crm.py`) so every run is reproducible. Three defects were introduced on purpose and are labelled in the code (`DEFECT-1`, `DEFECT-2`, `DEFECT-3`).

The flow mirrors the lead-generation and CRM automation systems I build for clients. No client code, data or credentials are used here.

## Problems considered

All numbers below come from `python scripts/measure.py baseline` → [`results/baseline.json`](results/baseline.json). They are measured on the fake CRM, on one machine, with synthetic inputs. The 200-lead batch uses a fault mix I chose (80% ok, 8% timeout after the CRM saved the record, 5% timeout before save, 4% two 500s, 3% permanent 400). Those rates are assumptions, not observed data.

| # | Problem | Where | Baseline evidence (measured, synthetic) |
|---|---|---|---|
| 1 | Unreliable retries: retries every error including permanent 4xx, 8 attempts, fixed 0.5 s sleep, no idempotency key | `app/crm_client.py` `push_lead` | Timeout after save → **2 contacts** for one lead. Permanent 400 → **8 CRM requests, 4.0 s** waiting, then 502. Batch: **20 duplicates / 200 leads**, **1.475 CRM requests per lead**, 51.5 s total waiting. |
| 2 | Duplicated scoring logic that has already drifted | inline copy in `app/main.py` vs `app/scoring.py` | **16 of 24** input combinations store a different score than `score_lead()` returns. Routing uses the canonical function, so routing is right; the stored score is wrong. |
| 3 | No email validation | `app/models.py` | **5 of 5** invalid emails (`""`, `not-an-email`, `a@`, …) accepted with 201 and written to the CRM. |

## Criteria and scores

Scored 1 (low) to 5 (high). Higher means more reason to fix now.

- **User impact** — harm to the lead and the sales team using the CRM.
- **Operating cost** — extra API calls, waiting, manual clean-up.
- **Maintenance effort** — how hard the current code makes safe change.

| # | User impact | Operating cost | Maintenance effort | Total |
|---|---|---|---|---|
| 1 Retries | 5 | 5 | 3 | **13** |
| 2 Duplicated scoring | 3 | 1 | 4 | 8 |
| 3 Missing validation | 3 | 2 | 1 | 6 |

Reasons:

- **#1 user impact 5:** duplicates mean the same person can be called or emailed twice by sales, and someone has to merge records by hand. When the CRM rejects a lead permanently, the user waits through 8 pointless attempts before getting an error.
- **#1 operating cost 5:** a permanent error costs 8 requests instead of 1. CRM APIs are rate-limited, so wasted calls during an outage also slow down healthy traffic.
- **#1 maintenance 3:** the retry policy is buried in a bare `except Exception` loop. You cannot change attempts or which errors retry without editing control flow.
- **#2:** real drift and annoying to maintain, but routing is unaffected and there is no extra runtime cost. It is the cheapest fix of the three, which is why it is first on the follow-up list, not why it should go first.
- **#3:** junk data, but low volume and no repeated cost.

## Why #1 ranked first

It is the only problem that both creates bad data (duplicates) and multiplies load on an external, rate-limited system. Its cost repeats on every failure, and failures are normal for a third-party API. The other two are real but contained.

## Affected users

- **Sales team** working the CRM: duplicate contacts, double outreach.
- **The lead** submitting the form: slow error on permanent failures, risk of being contacted twice.
- **Whoever owns the automation** (ops/engineer): manual de-duplication, wasted API quota.

These are roles, not interviewed people. No user research was done for this Quest.

## Intended value

- One form submission creates at most one CRM contact, even when a timeout hides a successful write.
- Permanent CRM errors fail fast (1 request, no waiting).
- Transient errors still recover, with fewer, spaced attempts.
- The retry policy is one small, named object that another engineer can change and test.

## Non-goals (what I will not change)

- The duplicated scoring logic (#2) and missing validation (#3). Left in place and still labelled.
- De-duplicating double submissions by the user (same form sent twice). Different problem; needs a product decision.
- A durable queue / outbox for leads that fail after all retries. Still returns 502, as today.
- Circuit breaker, async I/O, real CRM integration, real HTTP client.
- Any claim about production or team-wide impact. Results are from a local synthetic test.
