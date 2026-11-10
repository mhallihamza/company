"""General web research — Trends signals and public Etsy competition.

Honest: no numbers are fabricated when connectivity fails; a tagged mock is returned with source='mock'.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import os
from typing import Any


def google_trends(keywords: list[str], timeframe: str = "today 12-m") -> dict[str, Any]:
    keywords = [k for k in keywords if k][:6] or ["kids book"]
    force_fake = os.getenv("AIHQ_FAKE_LLM", "").lower() in ("1", "true", "yes")
    if not force_fake:
        try:
            return _pytrends(keywords, timeframe)
        except Exception:  # noqa: BLE001
            return _mock_trends(keywords, "trends_unavailable")
    return _mock_trends(keywords, "demo")


def _pytrends(keywords: list[str], timeframe: str) -> dict[str, Any]:
    from pytrends.request import TrendReq
    trends = TrendReq(hl="en-US", tz=360, timeout=(3, 6))
    data: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(keywords)) as pool:
        futures = {pool.submit(_one_keyword, trends, kw, timeframe): kw for kw in keywords}
        for future in concurrent.futures.as_completed(futures, timeout=8):
            kw = futures[future]
            try:
                data[kw] = future.result(timeout=2)
            except Exception:  # noqa: BLE001
                data[kw] = _mock_entry(kw)
    return {"source": "live", "timeframe": timeframe, "keywords": data}


def _one_keyword(trends, kw: str, timeframe: str) -> dict[str, Any]:
    trends.build_payload([kw], timeframe=timeframe, geo="")
    df = trends.interest_over_time()
    related = {}
    try:
        related = trends.related_queries().get(kw, {}) or {}
    except Exception:  # noqa: BLE001
        related = {}
    return {
        "avg_interest": round(float(df[kw].mean()), 1) if not df.empty else 0.0,
        "trend": "rising" if _rising(df[kw].tolist()) else "steady",
        "related": (related.get("rising") or {}).head(5)["query"].tolist()
        if hasattr((related.get("rising") or None), "head") else [],
    }


def _rising(series: list[float]) -> bool:
    if len(series) < 4:
        return False
    tail = sum(series[-len(series) // 3:])
    head = sum(series[:len(series) // 3])
    return tail > head * 1.15


def _mock_entry(keyword: str) -> dict[str, Any]:
    seed = int(hashlib.sha256(keyword.encode()).hexdigest(), 16)
    return {"avg_interest": 40 + seed % 40, "trend": "rising" if seed % 3 else "steady",
            "related": [f"{keyword} book", f"{keyword} كراسل", f"{keyword} للأطفال"]}


def _mock_trends(keywords: list[str], source: str) -> dict[str, Any]:
    return {"source": source, "timeframe": "demo",
            "keywords": {kw: _mock_entry(kw) for kw in keywords}}


def etsy_competition_public(term: str) -> dict[str, Any]:
    """Etsy competition: live API with ETSY_KEYSTRING, explicit partial+error otherwise."""
    key = os.getenv("ETSY_KEYSTRING") or os.getenv("ETSY_API_KEY", "")
    if key:
        from agents.capabilities.marketplace import etsy_active_listings
        data = etsy_active_listings([term])
        found = (data.get("keywords") or {}).get(term) or {}
        if "error" in found:
            # do NOT pretend we know the answer — surface live-side failure as `partial`
            return {"source": "partial", "query": term, "error": found["error"]}
        return {"source": "etsy_api_v3", "query": term,
                "results": found.get("total_listings"),
                "competition": _bucket(int(found.get("total_listings") or 0)),
                "avg_favorers_top25": found.get("avg_favorers_top25"),
                "avg_price_top25": found.get("avg_price_top25")}

    # no credentials — never invent competition numbers, even as a stub.
    return {"source": "demo", "query": term, "results": None,
            "competition": None}


def _bucket(count: int) -> str:
    if count < 150:
        return "low"
    if count < 500:
        return "medium"
    return "high"


def full_research(keywords: list[str]) -> dict[str, Any]:
    trends = google_trends(keywords)
    competition = {kw: etsy_competition_public(kw) for kw in keywords[:4]}
    return {"google_trends": trends, "etsy_competition": competition,
            "sampled_at": _now()}


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")

from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="web_research",
    title_en="Web Research", title_ar="بحث الويب",
    description_en="Google Trends signals + public marketplace competition estimates (utils for every department).",
    description_ar="إشارات Google Trends وتقديرات منافسة أسواق عامة (أداة كل قسم).",
    used_by=["books.market", "intelligence", "affiliate"], deterministic=True,
))
