from app.models import LeadIn


def score_lead(lead: LeadIn) -> int:
    """Simple lead score used for CRM routing (0-100)."""
    score = 10
    if lead.company:
        score += 20
    if lead.employees >= 50:
        score += 40
    elif lead.employees >= 10:
        score += 20
    if lead.source == "referral":
        score += 30
    return min(score, 100)
