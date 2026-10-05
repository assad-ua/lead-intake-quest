from fastapi import FastAPI, HTTPException

from app.crm_client import CRMClient, CRMError
from app.fake_crm import FakeCRM
from app.models import LeadIn
from app.scoring import score_lead


def create_app(crm_client: CRMClient | None = None) -> FastAPI:
    app = FastAPI(title="Lead intake (Quest sample)")
    client = crm_client or CRMClient(FakeCRM())

    @app.post("/leads", status_code=201)
    def submit_lead(lead: LeadIn):
        # DEFECT-2 (deliberate, labelled for the Quest): duplicated business
        # logic. This re-implements app/scoring.py inline and has already
        # drifted: it gives referral leads +25 instead of +30 and ignores
        # the 10-49 employee band. score_lead() is used for the routing tag,
        # this copy is what gets stored as `score`.
        score = 10
        if lead.company:
            score += 20
        if lead.employees >= 50:
            score += 40
        if lead.source == "referral":
            score += 25
        score = min(score, 100)

        route = "sales" if score_lead(lead) >= 50 else "nurture"
        payload = {**lead.model_dump(), "score": score, "route": route}
        try:
            contact = client.push_lead(payload)
        except CRMError:
            raise HTTPException(status_code=502, detail="Could not save lead to CRM")
        return {"crm_id": contact["id"], "score": score, "route": route}

    return app


app = create_app()
