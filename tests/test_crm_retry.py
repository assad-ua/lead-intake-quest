"""Retry and idempotency tests for CRMClient.push_lead (DEFECT-1 fix).

These fail on the baseline commit (fa8883f) and pass after the fix.
"""

import pytest
from fastapi.testclient import TestClient

from app.crm_client import CRMClient, CRMError
from app.fake_crm import FakeCRM
from app.main import create_app

PAYLOAD = {"name": "A", "email": "a@example.com"}


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


def client(script):
    crm, sleeps = FakeCRM(script), Sleeps()
    return CRMClient(crm, sleep=sleeps), crm, sleeps


def test_timeout_after_commit_does_not_duplicate():
    c, crm, _ = client(["timeout_after_commit", "ok"])
    c.push_lead(PAYLOAD)
    assert crm.requests == 2
    assert len(crm.contacts_for("a@example.com")) == 1


def test_permanent_400_fails_fast_without_sleeping():
    c, crm, sleeps = client(["400"])
    with pytest.raises(CRMError) as err:
        c.push_lead(PAYLOAD)
    assert crm.requests == 1
    assert sleeps == []
    assert err.value.__cause__.status == 400


def test_crm_down_stops_after_max_attempts_with_backoff():
    c, crm, sleeps = client(["500"])
    with pytest.raises(CRMError):
        c.push_lead(PAYLOAD)
    assert crm.requests == 3
    assert sleeps == pytest.approx([0.2, 0.4])


@pytest.mark.parametrize("first", ["429", "503", "timeout_before_commit"])
def test_transient_error_then_ok_recovers(first):
    c, crm, sleeps = client([first, "ok"])
    assert c.push_lead(PAYLOAD)["email"] == "a@example.com"
    assert crm.requests == 2
    assert sleeps == pytest.approx([0.2])


def test_same_key_on_every_attempt():
    seen = []

    class Recorder(FakeCRM):
        def post(self, path, json, headers):
            seen.append(headers["Idempotency-Key"])
            return super().post(path, json, headers)

    CRMClient(Recorder(["500", "500", "ok"]), sleep=lambda s: None).push_lead(PAYLOAD)
    assert len(seen) == 3 and len(set(seen)) == 1


def test_separate_submissions_get_separate_keys():
    crm = FakeCRM(["ok"])
    c = CRMClient(crm, sleep=lambda s: None)
    c.push_lead(PAYLOAD)
    c.push_lead(PAYLOAD)
    assert len(crm.contacts) == 2


def test_policy_is_configurable():
    from app.crm_client import RetryPolicy  # added by the fix

    crm, sleeps = FakeCRM(["500"]), Sleeps()
    c = CRMClient(crm, sleep=sleeps, policy=RetryPolicy(max_attempts=5, base_delay_s=0.1))
    with pytest.raises(CRMError):
        c.push_lead(PAYLOAD)
    assert crm.requests == 5
    assert sleeps == pytest.approx([0.1, 0.2, 0.4, 0.8])


def test_api_returns_one_contact_when_response_is_lost():
    crm = FakeCRM(["timeout_after_commit", "ok"])
    api = TestClient(create_app(CRMClient(crm, sleep=lambda s: None)))
    resp = api.post("/leads", json=PAYLOAD)
    assert resp.status_code == 201
    assert len(crm.contacts_for("a@example.com")) == 1
