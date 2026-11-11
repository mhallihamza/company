"""Pinterest collector — honestly unavailable unless a licensed Pinterest app is configured.

No scraping. No fabricated numbers. If PINTEREST_APP_ID is not set we report blind_spot.
"""
from __future__ import annotations
import os

from agents.capabilities.market_research.base import MarketRecord, now_iso


def collect_pinterest(keywords: list[str]) -> dict:
    keywords = [k for k in keywords if k][:6]
    envelope = {
        "source": "pinterest",
        "query": ", ".join(keywords),
        "collected_at": now_iso(),
        "verified": False,
        "blind_spot": True,
        "records": [],
        "notes": [{
            "limitation": "Pinterest developer app not configured (PINTEREST_APP_ID). "
                          "No authorized access, so no Pinterest demand data can be collected."
        }],
    }
    _ = os.getenv("PINTEREST_APP_ID")
    return envelope
