"""Google Trends collector — public, no key required (rate-limited)."""
from __future__ import annotations
import os

from agents.capabilities.market_research.base import MarketRecord, now_iso


def collect_trends(keywords: list[str], timeframe: str = "today 12-m") -> dict:
    keywords = [k for k in keywords if k][:6]
    force_fake = os.getenv("AIHQ_FAKE_LLM", "").lower() in ("1", "true", "yes")
    envelope = {
        "source": "google_trends",
        "query": ", ".join(keywords),
        "collected_at": now_iso(),
        "verified": False,
        "blind_spot": False,
        "timeframe": timeframe,
        "records": [],
        "notes": [],
    }
    if force_fake:
        envelope["notes"].append("demo_mode")
        envelope["blind_spot"] = True
        for kw in keywords:
            envelope["records"].append(MarketRecord(
                source="demo", market="Google Trends", data_type="trend_interest",
                title=kw, url=None, rating=None, verified=False, raw={"demo": True}))
        return envelope
    try:
        from pytrends.request import TrendReq
        import pandas as pd  # noqa: F401
        trends = TrendReq(hl="en-US", tz=360, timeout=(4, 8))
        for kw in keywords:
            try:
                trends.build_payload([kw], timeframe=timeframe, geo="")
                df = trends.interest_over_time()
                avg = round(float(df[kw].mean()), 1) if not df.empty else None
                series = df[kw].tolist() if not df.empty else []
                envelope["records"].append(MarketRecord(
                    source="google_trends", market="Google Trends", data_type="trend_interest",
                    title=kw, url=f"https://trends.google.com/trends/explore?q={kw.replace(' ', '%20')}",
                    captured_at=now_iso(), verified=True,
                    raw={"avg_interest": avg,
                         "sample_series": series[-12:] if series else [],
                         "length_months": len(df) if not df.empty else 0}))
            except Exception as e:  # noqa: BLE001
                envelope["notes"].append({"keyword": kw, "error": str(e)[:200]})
        envelope["verified"] = bool(envelope["records"]) and not envelope["notes"]
        return envelope
    except Exception as e:  # noqa: BLE001
        envelope["blind_spot"] = True
        envelope["notes"] = [{"error": f"pytrends_unavailable: {e}"}]
        return envelope
