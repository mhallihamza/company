"""Normalizer — clean up + dedupe collector records.

* URL-normalization (lowercase scheme/host, drop fragment, canonicalize path).
* Dedup by (source, normalized-url) tuple — keeps the highest-priority verified record.
* No invented fields. Missing = None.
* Returns plain dicts (JSON-safe) ready for the `research_sources`/`competitor_observations` tables.
"""
from __future__ import annotations
from agents.capabilities.market_research.base import MarketRecord


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    u = str(url).strip()
    # strip fragment
    if "#" in u:
        u = u.split("#", 1)[0]
    # drop trailing slash (except root)
    from urllib.parse import urlsplit, urlunsplit
    try:
        parts = urlsplit(u)
        cleaned = urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                              parts.path.rstrip("/") or "/", "", ""))
        return cleaned
    except Exception:  # noqa: BLE001
        return u


def normalize_records(raw_records: list[dict]) -> list[dict]:
    seen: dict[tuple[str, str | None], dict] = {}
    for rec in raw_records:
        source = str(rec.get("source") or "").lower()
        url = normalize_url(rec.get("url"))
        row = MarketRecord(
            source=source,
            market=str(rec.get("market") or "").title(),
            data_type=str(rec.get("data_type") or ""),
            title=str(rec.get("title") or ""),
            url=url,
            price=rec.get("price"), rating=rec.get("rating"), reviews=rec.get("reviews"),
            captured_at=rec.get("captured_at"), verified=bool(rec.get("verified")),
            raw=rec.get("raw") or {})
        key = (source, url)
        prev = seen.get(key)
        if prev is None or (not prev.get("verified") and row.get("verified")):
            seen[key] = row
    return list(seen.values())
