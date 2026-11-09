"""unit_economics — حدود رسوم Etsy/KDP المنشورة وحساب الوحدة بالـ Python الحتمي."""
from __future__ import annotations

# رسوم فعلية معلنة (راجع الصفحات الرسمية دورياً للتحديث)
ETSY = {"listing_fee_usd": 0.20, "transaction_pct": 0.065, "payment_pct": 0.03}
KDP = {"paperback_royalty": 0.60, "kdp_ebook_35": 0.35, "kdp_ebook_70": 0.70,
       "delivery_per_mb": 0.15}


def unit_economics(price: float, pages: int, item: str = "book") -> dict:
    price = float(price)
    etsy_var = price * (ETSY["transaction_pct"] + ETSY["payment_pct"])
    etsy_per_sale = ETSY["listing_fee_usd"] + etsy_var
    return {
        "price": price, "pages": pages, "item": item,
        "etsy": {"per_sale_costs": round(etsy_per_sale, 2),
                 "net_before_ads": round(price - etsy_per_sale, 2)},
        "kdp_paperback": {"royalty_60_pct": round(price * KDP["paperback_royalty"], 2),
                          "note": "اخصم Print cost من حاسبة KDP الرسمية للحصول على صافي الهوامش"},
        "kdp_ebook": {"royalty_70_pct": round(price * KDP["kdp_ebook_70"], 2),
                      "royalty_35_pct": round(price * KDP["kdp_ebook_35"], 2),
                      "delivery_per_mb_usd": KDP["delivery_per_mb"]},
        "assumptions": ["USD", "رقمي = لا كلفة طباعة", "الطباعة تطبق فقط على paperback",
                        "الرسوم تتغير — راجع صفحتي Etsy/KDP الرسمية"],
    }


from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="unit_economics",
    title_en="Unit Economics", title_ar="حسابات الوحدة",
    description_en="Published Etsy and KDP fee models; Python-only math — never LLM arithmetic.",
    description_ar="نماذج رسوم Etsy وKDP المنشورة؛ حساب Python حصري — النموذج لا يحسب أبداً.",
    used_by=["finance", "affiliate"], deterministic=True,
))
