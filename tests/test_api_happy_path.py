"""Pre-existing happy-path tests (written with the baseline service)."""

from fastapi.testclient import TestClient

from app.crm_client import CRMClient
from app.fake_crm import FakeCRM
from app.main import create_app


def make_api(script=("ok",)):
    crm = FakeCRM(list(script))
    return TestClient(create_app(CRMClient(crm, sleep=lambda s: None))), crm


def test_lead_is_created_in_crm():
    api, crm = make_api()
    resp = api.post("/leads", json={"name": "A", "email": "a@example.com", "company": "Acme"})
    assert resp.status_code == 201
    assert len(crm.contacts_for("a@example.com")) == 1


def test_large_company_routes_to_sales():
    api, _ = make_api()
    resp = api.post("/leads", json={"name": "A", "email": "a@example.com",
                                    "company": "Acme", "employees": 200})
    assert resp.json()["route"] == "sales"
