"""Source registry — which collectors are configured, and which are not.

Never raises from a caller perspective. Returns only *capability descriptions*,
never live calls. Collection logic lives in the per-source collectors.
"""
from __future__ import annotations
import os

_REGISTRY = {
    "amazon_kdp": {
        "title": "Amazon KDP (publishing intelligence)",
        "source_url": "https://kdp.amazon.com/en_US/help",
        "live_mode": "Amazon has NO public competitor-data API. Verified via Etsy/Trends proxies.",
        "status": "manual_input_only",
        "needs_env": [],
    },
    "etsy": {
        "title": "Etsy Open API v3",
        "source_url": "https://developers.etsy.com/",
        "live_mode": "x-api-key with keystring:shared_secret",
        "status": "api_available",
        "needs_env": ["ETSY_KEYSTRING", "ETSY_SHARED_SECRET"],
    },
    "google_trends": {
        "title": "Google Trends",
        "source_url": "https://trends.google.com/",
        "live_mode": "pytrends (no key required; rate-limited)",
        "status": "api_available",
        "needs_env": [],
    },
    "pinterest": {
        "title": "Pinterest",
        "source_url": "https://developers.pinterest.com/",
        "live_mode": "OAuth2 app credentials — not configured here.",
        "status": "manual_input_only",
        "needs_env": ["PINTEREST_APP_ID"],
    },
}


def get_enabled_sources() -> dict[str, bool]:
    return {
        "amazon_kdp": True,                                  # always probing (honest empty)
        "etsy": bool((os.getenv("ETSY_KEYSTRING") or "").strip()),
        "google_trends": True,                               # always attempted; may fall back silently
        "pinterest": bool((os.getenv("PINTEREST_APP_ID") or "").strip()),
    }


def source_available(name: str) -> dict:
    info = dict(_REGISTRY.get(name) or {})
    info["env_ok"] = bool(all(os.getenv(e) for e in info.get("needs_env", []) if os.getenv(e)))
    return info
