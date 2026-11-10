"""market_profiles access helpers — shared by the opportunity engine and books.content.

Never guesses: returns only ENABLED profiles. Unknown requested market → None (fail fast
at the caller with an actionable message).
"""
from __future__ import annotations
from typing import Any


def load_enabled_profiles() -> list[dict[str, Any]]:
    """All enabled market profiles, ordered for deterministic default selection.

    Auto-seeds the starter markets (us-en / fr-fr / sa-ar) when the table is missing
    or empty — engine works on a fresh install without manual bootstrap.
    """
    from backend.app.db import get_store

    def _query():
        return get_store().q("SELECT * FROM market_profiles WHERE enabled ORDER BY country, language")

    try:
        rows = _query()
    except Exception:  # noqa: BLE001 — table missing: create+seed
        rows = []
    if not rows:
        try:
            from backend.app.routers.profiles import seed
            seed()
            rows = _query()
        except Exception:  # noqa: BLE001
            return []
    out = []
    for r in rows:
        p = dict(r)
        try:
            p["label"] = f"{str(p.get('country', '')).lower()}-{str(p.get('language', '')).lower()}"
        except Exception:  # noqa: BLE001
            p["label"] = "unknown"
        out.append(p)
    return out


def pick_profile(market: str | None) -> dict[str, Any] | None:
    """Pick one enabled profile. None when nothing is enabled or the requested one is missing."""
    markets = load_enabled_profiles()
    if not markets:
        return None
    if market:
        target = str(market).strip().lower().replace("_", "-")
        for p in markets:
            if target in (p["label"], str(p.get("country", "")).lower()):
                return p
        return None
    for p in markets:
        if p["label"] == "us-en":
            return p
    return markets[0]
