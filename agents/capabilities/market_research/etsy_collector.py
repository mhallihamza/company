"""Etsy collector — permitted Etsy Open API v3 read.

With no ETSY_KEYSTRING there are NO listings, NO prices, NO review counts and
NO favorites — silently returning made-up numbers would break the whole point.
"""
from __future__ import annotations
import os

from agents.capabilities.market_research.base import MarketRecord, now_iso


def collect_etsy(keywords: list[str]) -> dict:
    keywords = [k for k in keywords if k][:6]
    key = (os.getenv("ETSY_KEYSTRING") or os.getenv("ETSY_API_KEY") or "").strip()
    envelope = {
        "source": "etsy",
        "query": ", ".join(keywords),
        "collected_at": now_iso(),
        "verified": False,
        "blind_spot": True,
        "limitation": None,
        "records": [],
        "notes": [],
    }
    if not key:
        envelope["limitation"] = (
            "ETSY_KEYSTRING is empty. Etsy live competition data is unavailable. "
            "Set ETSY_KEYSTRING + ETSY_SHARED_SECRET to enable the v3 API.")
        return envelope

    # Live path — only use existing etsy_active_listings (already built & hardened)
    from agents.capabilities.marketplace import etsy_active_listings
    res = etsy_active_listings(keywords)
    kw_hits = (res.get("keywords") or {})
    errs = []
    for kw in keywords:
        hit = kw_hits.get(kw) or {}
        if "error" in hit:
            errs.append({"keyword": kw, "error": hit["error"]})
            continue
        rec = MarketRecord(
            source="etsy_api_v3",
            market="Etsy",
            data_type="listing",
            title=f"{hit.get('total_listings') or '?'} listings for '{kw}'",
            url=(hit.get("url") or f"https://www.etsy.com/search?q={kw.replace(' ', '+')}"),
            raw=hit,
            verified=True,
        )
        envelope["records"].append(rec)
    if errs:
        envelope["notes"] = errs
        envelope["verified"] = False
        envelope["blind_spot"] = bool(len(errs) == len(keywords))
        envelope["limitation"] = f"Etsy API returned errors for {len(errs)}/{len(keywords)} keyword(s)."
    else:
        envelope["verified"] = True
        envelope["blind_spot"] = False
    return envelope
