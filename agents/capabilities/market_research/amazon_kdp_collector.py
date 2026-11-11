"""Amazon KDP collector.

Amazon does **not** provide a public competitor-data API for KDP. Inventing
one is a fabrication. What we CAN honestly do:

  1. Return a structured `blind_spot` with the live-side limitation spelled out.
  2. Ask the founder / an operator to paste competitor listings as CSV for ingestion.
  3. Use public, permitted Etsy findings as the closest proxy and clearly label them as Etsy, not KDP.

This collector NEVER fabricates ratings, counts, prices or best-seller ranks.
"""
from __future__ import annotations
from agents.capabilities.market_research.base import MarketRecord, now_iso


def collect_kdp(keywords: list[str], *, manual_records: list[dict] | None = None) -> dict:
    keywords = [k for k in keywords if k][:6]

    envelope = {
        "source": "amazon_kdp",
        "query": ", ".join(keywords),
        "collected_at": now_iso(),
        "verified": False,
        "blind_spot": True,
        "limitation": (
            "Amazon provides no public KDP competitor-data API. Ratings, review counts,"
            "BSR and bestsellers ranks cannot be legally read programmatically without"
            "an authorized provider. Provide a licensed provider or paste CSV manually to fill this in."
        ),
        "records": [],
        "notes": [],
    }

    if manual_records:
        envelope["blind_spot"] = False
        envelope["verified"] = True
        recs = []
        for row in manual_records:
            try:
                recs.append(MarketRecord(
                    source="amazon_kdp_manual",
                    market=(row.get("marketplace") or "amazon").title(),
                    data_type=str(row.get("format") or "book"),
                    title=str(row.get("title") or "untitled"),
                    url=row.get("url"), price=row.get("price"),
                    rating=row.get("rating"), reviews=row.get("reviews"),
                    captured_at=now_iso(), verified=True, raw=row))
            except Exception:  # noqa: BLE001
                envelope["notes"].append({"malformed_row": row})
        envelope["records"] = recs
    return envelope
