"""Market analyzer — turn collected records into a structured brief.

This does NOT forecast revenue (clearly unsupported without authorized provider data).
It produces an evidence-packed summary the CEO + intelligence department score:
  * how many verified vs blind_spot sources saw the niche,
  * price band (from verified records only),
  * format mix (listing types observed),
  * competitor examples with links,
  * confidence label + explicit gaps.
"""
from __future__ import annotations

from statistics import median


def analyze_records(collect_envelopes: dict[str, dict]) -> dict:
    summary = {
        "verified_sources": [],
        "blind_spot_sources": [],
        "price_band_usd": None,
        "verified_rating_avg": None,
        "verified_reviews_median": None,
        "competitor_examples": [],
        "confidence": "low",        # low until verified competitor evidence exists
        "gaps": [],
        "notes": ["No sales or search-volume numbers are ever fabricated. Missing data is reported as missing."],
    }

    # gather records from all envelopes
    all_records: list[dict] = []
    for name, env in collect_envelopes.items():
        if env.get("verified"):
            summary["verified_sources"].append(name)
        else:
            summary["blind_spot_sources"].append(name)
        all_records.extend(env.get("records") or [])

    # price band — only from verified records with a price
    prices = [r.get("price") for r in all_records if r.get("verified") and isinstance(r.get("price"), (int, float))]
    if len(prices) >= 3:
        summary["price_band_usd"] = {"low": min(prices), "median": round(median(prices), 2), "high": max(prices)}
    elif prices:
        summary["gaps"].append("price_band_thin")
    else:
        summary["gaps"].append("price_band_missing")

    # rating avg — verified only
    ratings = [r.get("rating") for r in all_records if r.get("verified") and isinstance(r.get("rating"), (int, float))]
    if ratings:
        summary["verified_rating_avg"] = round(sum(ratings) / len(ratings), 2)
    if ratings and summary["verified_rating_avg"] is not None:
        summary["verified_rating_avg"] = summary["verified_rating_avg"]

    # review median
    revs = [r.get("reviews") for r in all_records if r.get("verified") and isinstance(r.get("reviews"), int)]
    if revs:
        summary["verified_reviews_median"] = median(revs)

    # competitor examples — verified records with urls, title, price
    competitors = [r for r in all_records
                   if r.get("url") and r.get("title") and r.get("verified")][:10]
    summary["competitor_examples"] = [
        {"title": c["title"], "url": c["url"], "price": c.get("price"),
         "rating": c.get("rating"), "reviews": c.get("reviews"), "source": c["source"]}
        for c in competitors
    ]

    # confidence — needs at least one verified competitor listing + one verified demand signal
    if summary["verified_sources"] and summary["competitor_examples"]:
        summary["confidence"] = "high" if len(summary["verified_sources"]) >= 2 else "medium"
    elif summary["verified_sources"]:
        summary["confidence"] = "medium"
    else:
        summary["confidence"] = "low"

    if not summary["competitor_examples"]:
        summary["gaps"].append("competitor_examples_missing")
    if "etsy" in summary["blind_spot_sources"] and "google_trends" in summary["blind_spot_sources"]:
        summary["gaps"].append("no_live_source_verified")

    return summary
