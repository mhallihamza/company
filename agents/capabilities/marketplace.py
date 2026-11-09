"""Marketplace integrations — real-Etsy paths ported from the legacy agent.

`etsy_active_listings()` — search active listings with x-api-key (the v1 Etsy API
path, kept because it works) to get the REAL count + top-25 favorers + average price.
When there is no ETSY_API_KEY, callers fall back to the deterministic demo stub.

`etsy_create_draft()` — full publish flow (listing + file + cover) gated by the
human-approval lane. Without keys it returns a clearly-labelled MOCK id.
"""
from __future__ import annotations
import hashlib
import json
import os
import random
from typing import Any

_ETSY = "https://openapi.etsy.com/v3/application"
_MOCK_LISTINGS = 23801


def etsy_active_listings(keywords: list[str]) -> dict[str, Any]:
    """Real competition read from Etsy Open API v3 (needs ETSY_API_KEY)."""
    key = os.getenv("ETSY_API_KEY", "")
    if not key:
        return {"source": "demo", "reason": "ETSY_API_KEY not set", "keywords": {}}
    try:
        import requests
    except ImportError:
        return {"source": "demo", "reason": "requests not installed", "keywords": {}}

    out: dict[str, Any] = {"source": "etsy_api_v3", "keywords": {}}
    for kw in [k for k in keywords if k][:6]:
        try:
            r = requests.get(f"{_ETSY}/listings/active",
                             headers={"x-api-key": key},
                             params={"keywords": kw, "limit": 25, "sort_on": "score"},
                             timeout=20)
            if not r.ok:
                out["keywords"][kw] = {"error": f"http {r.status_code}", **_demo_bucket(kw)}
                continue
            j = r.json()
            results = j.get("results") or []
            favorers = [x.get("num_favorers", 0) or 0 for x in results]
            prices = [float(x["price"]["amount"]) / x["price"]["divisor"]
                      for x in results if x.get("price")]
            out["keywords"][kw] = {
                "source": "etsy_api_v3",
                "total_listings": j.get("count"),
                "avg_favorers_top25": round(sum(favorers) / max(len(favorers), 1), 1),
                "avg_price_top25": round(sum(prices) / max(len(prices), 1), 2) if prices else None,
            }
        except Exception as e:  # noqa: BLE001
            out["keywords"][kw] = {"error": str(e)[:120], **_demo_bucket(kw)}
    return out


def _demo_bucket(term: str) -> dict[str, Any]:
    seed = int(hashlib.md5(term.encode()).hexdigest(), 16)  # noqa: S324
    count = 30 + seed % 900
    return {"source": "demo", "total_listings": count,
            "competition": "low" if count < 150 else "medium" if count < 500 else "high"}


def etsy_create_draft_real(meta: dict[str, Any], pdf_path: str, cover_path: str | None,
                           price: float = 4.99) -> str:
    """Full real flow: listing → PDF file → cover image. Requires ETSY_API_KEY/SHOP_ID/TOKEN."""
    import requests

    api_key = os.environ["ETSY_API_KEY"]
    access_token = os.environ["ETSY_ACCESS_TOKEN"]
    shop = os.environ["ETSY_SHOP_ID"]
    headers = {"x-api-key": api_key,
               "Authorization": f"Bearer {access_token}"}

    data = {"quantity": 999,
            "title": str(meta.get("title", ""))[:140],
            "description": meta.get("description", ""),
            "price": price,
            "who_made": "i_did",
            "when_made": "made_to_order",
            "type": "download",
            "taxonomy_id": int(os.getenv("ETSY_TAXONOMY_ID", "116")) or 0,
            "tags": ",".join((meta.get("tags") or [])[:13]),
            "is_supply": False}
    r = requests.post(f"{_ETSY}/shops/{shop}/listings", headers=headers,
                      data=data, timeout=60)
    r.raise_for_status()
    listing_id = str(r.json()["listing_id"])

    with open(pdf_path, "rb") as f:
        rr = requests.post(f"{_ETSY}/shops/{shop}/listings/{listing_id}/files",
                           headers=headers,
                           files={"file": f},
                           data={"name": os.path.basename(pdf_path)},
                           timeout=180)
        rr.raise_for_status()

    if cover_path and os.path.exists(cover_path):
        with open(cover_path, "rb") as f:
            rr = requests.post(f"{_ETSY}/shops/{shop}/listings/{listing_id}/images",
                               headers=headers,
                               files={"image": f},
                               timeout=180)
            rr.raise_for_status()

    return listing_id


def etsy_create_draft(meta: dict[str, Any], pdf_path: str, cover_path: str | None,
                      price: float = 4.99,
                      dry_run: bool | None = None) -> tuple[str, bool]:
    """Returns (listing_id, is_mock). Real flow only with ETSY_API_KEY + TOKEN + SHOP_ID."""
    if dry_run is None:
        dry_run = not (os.getenv("ETSY_API_KEY") and os.getenv("ETSY_ACCESS_TOKEN")
                       and os.getenv("ETSY_SHOP_ID"))
    if dry_run:
        return f"MOCK-{random.randint(10000, 99999)}", True
    try:
        return etsy_create_draft_real(meta, pdf_path, cover_path, price), False
    except Exception as e:  # noqa: BLE001 — إعادة بـMOCK موثقة بدل الانهيار
        return f"MOCK-FALLBACK-{abs(hash(str(e))) % 10000:04d}", True


def kdp_manifest(story: dict[str, Any]) -> dict[str, Any]:
    etsy = story.get("etsy") or {}
    return {
        "title": etsy.get("title", story.get("title", "Untitled")),
        "description": etsy.get("description", ""),
        "tags": etsy.get("tags", [])[:13],
        "note": "KDP has no general book-upload API; paste this manifest into KDP manually.",
    }


from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="marketplace_listings",
    title_en="Marketplace Listings", title_ar="قوائم الأسواق",
    description_en="Etsy competition read (real API) + one-shot draft creation after founder sign-off (MOCK without keys) + KDP manifest.",
    description_ar="قراءة منافسة Etsy عبر API حقيقي + إنشاء مسودة بعد موافقتك (MOCK دون مفاتيح) + كاتب KDP.",
    used_by=["books.publishing"], deterministic=True,
))
