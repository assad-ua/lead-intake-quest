"""Reproducible before/after measurement for the lead-intake flow.

Run:  python scripts/measure.py <label>      (writes results/<label>.json)

Everything here is SYNTHETIC: a fake in-process CRM driven by fixed
outcome scripts and a seeded random batch. Numbers are measured on this
fake, on one machine. They show the behaviour of the code, not the cost
in any real production system.

Waiting time is measured by recording the sleep() calls the client makes
(simulated seconds), so the run is fast and deterministic.
"""

import json
import random
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.crm_client import CRMClient
from app.fake_crm import FakeCRM
from app.main import create_app
from app.models import LeadIn
from app.scoring import score_lead

ROOT = Path(__file__).resolve().parent.parent

LEAD = {"name": "Test Lead", "email": "lead@example.com", "company": "Acme", "employees": 20}

SCENARIOS = {
    "healthy": ["ok"],
    "transient_timeout_then_ok": ["timeout_before_commit", "ok"],
    "timeout_after_commit_then_ok": ["timeout_after_commit", "ok"],
    "rate_limited_then_ok": ["429", "ok"],
    "crm_rejects_400": ["400"],
    "crm_down_500": ["500"],
}


class SleepRecorder:
    def __init__(self):
        self.total = 0.0

    def __call__(self, seconds):
        self.total += seconds


def run_one(script, lead=LEAD):
    crm = FakeCRM(script)
    sleeper = SleepRecorder()
    api = TestClient(create_app(CRMClient(crm, sleep=sleeper)))
    t0 = time.perf_counter()
    resp = api.post("/leads", json=lead)
    wall_ms = (time.perf_counter() - t0) * 1000
    return {
        "http_status": resp.status_code,
        "crm_requests": crm.requests,
        "contacts_created": len(crm.contacts_for(lead["email"])),
        "simulated_wait_s": round(sleeper.total, 2),
        "wall_ms": round(wall_ms, 1),
    }


def run_batch(n=200, seed=42):
    """SYNTHETIC fault mix. Rates are assumptions, not observed data."""
    rng = random.Random(seed)
    mix = [
        (0.80, ["ok"]),
        (0.08, ["timeout_after_commit", "ok"]),
        (0.05, ["timeout_before_commit", "ok"]),
        (0.04, ["500", "500", "ok"]),
        (0.03, ["400"]),
    ]
    totals = {"leads": n, "crm_requests": 0, "duplicate_contacts": 0,
              "failed_submissions": 0, "simulated_wait_s": 0.0}
    for i in range(n):
        r, acc = rng.random(), 0.0
        for p, script in mix:
            acc += p
            if r < acc:
                break
        lead = {**LEAD, "email": f"lead{i}@example.com"}
        res = run_one(list(script), lead)
        totals["crm_requests"] += res["crm_requests"]
        totals["duplicate_contacts"] += max(0, res["contacts_created"] - 1)
        totals["failed_submissions"] += res["http_status"] >= 400
        totals["simulated_wait_s"] += res["simulated_wait_s"]
    totals["simulated_wait_s"] = round(totals["simulated_wait_s"], 2)
    totals["crm_requests_per_lead"] = round(totals["crm_requests"] / n, 3)
    return totals


def scoring_drift():
    """Problem 2 baseline: stored score vs the canonical score_lead()."""
    grid = []
    for company in ["", "Acme"]:
        for employees in [0, 5, 10, 49, 50, 500]:
            for source in ["website", "referral"]:
                grid.append({"name": "x", "email": "x@example.com",
                             "company": company, "employees": employees, "source": source})
    mismatches = 0
    for lead in grid:
        api = TestClient(create_app(CRMClient(FakeCRM(["ok"]), sleep=lambda s: None)))
        stored = api.post("/leads", json=lead).json()["score"]
        if stored != score_lead(LeadIn(**lead)):
            mismatches += 1
    return {"inputs": len(grid), "score_mismatches": mismatches}


def validation_gaps():
    """Problem 3 baseline: invalid emails the API accepts."""
    bad = ["", "not-an-email", "a@", "@b.com", "a b@c.com"]
    accepted = 0
    for email in bad:
        res = run_one(["ok"], {**LEAD, "email": email})
        accepted += res["http_status"] == 201
    return {"invalid_inputs": len(bad), "accepted": accepted}


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    out = {
        "label": label,
        "note": "SYNTHETIC fake CRM, single local run; see scripts/measure.py",
        "scenarios": {name: run_one(list(s)) for name, s in SCENARIOS.items()},
        "batch_200_synthetic": run_batch(),
        "scoring_drift": scoring_drift(),
        "validation_gaps": validation_gaps(),
    }
    (ROOT / "results").mkdir(exist_ok=True)
    path = ROOT / "results" / f"{label}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")

    print(f"{'scenario':32} {'http':>5} {'reqs':>5} {'contacts':>9} {'wait_s':>7}")
    for name, r in out["scenarios"].items():
        print(f"{name:32} {r['http_status']:>5} {r['crm_requests']:>5} "
              f"{r['contacts_created']:>9} {r['simulated_wait_s']:>7}")
    print("batch:", out["batch_200_synthetic"])
    print("scoring:", out["scoring_drift"])
    print("validation:", out["validation_gaps"])
    print("written:", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
