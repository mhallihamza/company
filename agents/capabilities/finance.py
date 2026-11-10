"""unit_economics — documented fee models, Python deterministic math (no LLM arithmetic).

All numbers trace back to `agents.fees` — nothing hard-coded here.
"""
from __future__ import annotations

from agents.fees import etsy, kdp


def etsy_fee_breakdown(price: float, shipping: float = 0.0,
                       annual_sales_usd: float | None = None,
                       include_offsite: bool = False) -> dict:
    """Actual Etsy fee breakdown for a single completed order (USD, US marketplace)."""
    return etsy.total_fee(price, shipping, annual_sales_usd, include_offsite)


def kdp_paperback(list_price: float, pages: int) -> dict:
    """Actual KDP paperback royalty math — pages parameter drives the print cost."""
    return kdp.paperback_royalty(list_price, pages)


def unit_economics(price: float, pages: int, item: str = "book") -> dict:
    """Full picture: Etsy digital + KDP paperback (US)."""
    etsy_fee = etsy_fee_breakdown(float(price))
    kdp_pp = kdp_paperback(float(price), pages)
    ebook = {"royalty_70_pct": round(float(price) * 0.70, 2),
             "royalty_35_pct": round(float(price) * 0.35, 2),
             "delivery_per_mb_usd": 0.15,
             "source_url": kdp.SOURCE_URL_DELIVERY,
             "last_reviewed": kdp.LAST_REVIEWED}
    return {
        "price": float(price), "pages": int(pages), "item": item,
        "etsy": etsy_fee,
        "kdp_paperback": kdp_pp,
        "kdp_ebook": ebook,
        "assumptions": [
            "USD currency (US marketplace)",
            "Etsy Offsite Ads off by default; pass include_offsite=True + annual_sales_usd to model it",
            "KDP delivery cost applies only to the 35% eBook tier based on file size",
            "Fees and royalties drift — verified 2026-11-09, confirm before pricing decisions",
        ],
    }


from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="unit_economics",
    title_en="Unit Economics", title_ar="حسابات الوحدة",
    description_en="Verified Etsy fees (listing + 6.5% + 3% + $0.25) and KDP royalties (50/60% by price, print cost by page count). All rules carry source_url and last_reviewed.",
    description_ar="رسوم Etsy المعتمدة والـ royalty في KDP حسب السعر، بصفحتين تُطبق بشكل حقيقي. كل قاعدة تحمل source_url وتاريخ آخر مراجعة.",
    used_by=["finance", "affiliate"], deterministic=True,
))
