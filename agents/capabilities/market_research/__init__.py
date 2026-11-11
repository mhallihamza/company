"""Market research module — typed collectors for KDP/Etsy/Trends.

Public surface:
  * `collect_kdp(keyword_list)`   — KDP (no public API → honest blind_spot + manual pathway)
  * `collect_etsy(keyword_list)`  — Etsy Open API v3 (requires ETSY_KEYSTRING etc.)
  * `collect_trends(keyword_list)`— Google Trends via pytrends (no key needed)
  * `collect_all(keywords)`       — runs enabled collectors, returns per-source envelopes
"""

from agents.capabilities.market_research.base import MarketRecord, now_iso
from agents.capabilities.market_research.source_registry import (
    get_enabled_sources, source_available,
)
from agents.capabilities.market_research.amazon_kdp_collector import collect_kdp
from agents.capabilities.market_research.etsy_collector import collect_etsy
from agents.capabilities.market_research.google_trends_collector import collect_trends
from agents.capabilities.market_research.data_normalizer import normalize_records
from agents.capabilities.market_research.market_analyzer import analyze_records
from agents.capabilities.market_research.pinterest_collector import collect_pinterest

__all__ = [
    "MarketRecord", "now_iso",
    "get_enabled_sources", "source_available",
    "collect_kdp", "collect_etsy", "collect_trends", "collect_pinterest",
    "normalize_records", "analyze_records", "collect_all",
]


def collect_all(keywords, task_id=None):
    out = {}
    if get_enabled_sources().get("amazon_kdp"):
        out["amazon_kdp"] = collect_kdp(keywords)
    if get_enabled_sources().get("etsy"):
        out["etsy"] = collect_etsy(keywords)
    if get_enabled_sources().get("google_trends"):
        out["google_trends"] = collect_trends(keywords)
    if get_enabled_sources().get("pinterest"):
        out["pinterest"] = collect_pinterest(keywords)
    return out
