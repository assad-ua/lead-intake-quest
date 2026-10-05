from pydantic import BaseModel


class LeadIn(BaseModel):
    """Lead submitted by the website contact form.

    DEFECT-3 (deliberate, labelled for the Quest): no validation.
    `email` is a plain string, so "not-an-email" or "" is accepted and
    only fails later when the CRM rejects it.
    """

    name: str
    email: str
    company: str = ""
    employees: int = 0
    source: str = "website"
