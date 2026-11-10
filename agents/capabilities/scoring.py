"""opportunity_scoring — documented 0-10 score for Affiliate/Intelligence."""
from __future__ import annotations

DEMAND_SCORE = {"high": 8.0, "rising": 8.0, "steady": 6.0, "low": 3.0, "unknown": 5.0}
COMPETITION_SCORE = {"low": 9.0, "medium": 5.0, "high": 3.0, "unknown": 5.0}


def score_candidate(c: dict) -> dict:
    """Documented formula: 35% demand, 25% competition, 25% commission (cap 15%), 15% cookie window (cap 30 days)."""
    price = float(c.get("est_price") or 0)
    pct = float(c.get("commission") or 0)
    cookie = float(c.get("cookie_days") or 14)
    demand = str(c.get("demand", "unknown")).lower()
    comp = str(c.get("competition", "unknown")).lower()
    risks: list[str] = []
    if comp == "high":
        risks.append("منافسة عالية")
    if cookie <= 7:
        risks.append("نافذة روابط قصيرة")
    if demand in ("low", "unknown"):
        risks.append("طلب ضعيف أو غير مؤكد")
    score = max(0.0, min(10.0,
        DEMAND_SCORE.get(demand, 5.0) * 0.35
        + COMPETITION_SCORE.get(comp, 5.0) * 0.25
        + min(pct / 15.0, 1.0) * 10 * 0.25
        + min(cookie / 30.0, 1.0) * 10 * 0.15))
    return {**c,
            "unit_commission": round(price * pct / 100.0, 2),
            "score": round(score, 1),
            "risks": risks}


from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="opportunity_scoring",
    title_en="Opportunity Scoring", title_ar="تسجيل الفرص",
    description_en="Documented deterministic scoring (0-10) combining demand, competition, commission and cookie window.",
    description_ar="تسجيل مرجعي موثق (0-10) يجمع الطلب والمنافسة والعمولة ونافذة الرابط.",
    used_by=["affiliate", "intelligence", "product"], deterministic=True,
))
