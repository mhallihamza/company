"""Market research collectors — typed, sourced-typed adapters for KDP / Etsy / Trends.

Every collector returns the same envelope:

    {
      "source": "etsyApiV3" | "amazonKdp" | "googleTrends" | "pinterest" | "demo",
      "query": "<keywords>",
      "collected_at": "2026-…Z",
      "verified": bool,          # False when live-side gives partial/error
      "blind_spot": bool,        # True when we lack data and refuse to guess
      "raw": {...},              # raw observation as returned (may be absent for errors)
      "normalized": {...},       # cleaned + typed records (deduplicated)
      "records": [<MarketRecord>…],
    }

Rules that keep us honest:
  * No live keys → `verified=false, blind_spot=true` and NO numbers.
  * Any live error → `verified=false`. We never upgrade a failed call to "live".
  * Missing metrics are `None`, never guessed.
  * Dedup keys are stable (url-normalized or source id).
"""

__all__ = ["MarketRecord"]


class MarketRecord(dict):
    """Typed thin wrapper — a single observation kept in the DB."""

    def __init__(self, source: str, market: str, data_type: str, title: str,
                 url: str | None = None, price: float | None = None,
                 rating: float | None = None, reviews: int | None = None,
                 captured_at: str | None = None, verified: bool = False,
                 raw: dict | None = None):
        super().__init__()
        self.update({
            "source": source,
            "market": market,
            "data_type": data_type,
            "title": (title or "").strip()[:500],
            "url": (url or "").strip(),
            "price": float(price) if price is not None else None,
            "rating": float(rating) if rating is not None else None,
            "reviews": int(reviews) if reviews is not None else None,
            "captured_at": captured_at,
            "verified": bool(verified),
            "raw": raw or {},
        })


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
