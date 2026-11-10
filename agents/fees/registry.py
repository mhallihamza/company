"""Fee model registry — the ONLY supported fee sources.

Every registered model carries:
  verified: True  → numbers sourced from the marketplace's official help pages
                     (with source_url + last_reviewed). Safe to use for unit economics.
  verified: False → NOT verified. Numeric fields are None and calculations return
                     source='partial'. Never auto-charge or quote from these.

`unit_economics()` is the single calculation path — it refuses to invent numbers.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FeeModel:
    ref: str                       # 'etsy.us', 'etsy.eu', 'kdp.us', …
    marketplace: str               # 'Etsy', 'KDP'
    region: str                    # 'US', 'EU', 'GLOBAL'
    currency: str                  # USD, EUR, …
    verified: bool
    listing_fee: float | None
    transaction_pct: float | None
    transaction_fixed: float | None
    payment_pct: float | None
    payment_fixed: float | None
    source_url: str | None
    last_reviewed: str | None
    notes: str


_UNSET_NOTE = ("No verified fee schedule on file for this marketplace. "
               "Do not auto-charge or quote fees from this model — verify on the "
               "marketplace help pages first.")

_ETSY_US_URL = "https://help.etsy.com/hc/en-us/articles/115015617766-What-are-the-fees-and-payments-on-Etsy-"
_KDP_US_URL = "https://kdp.amazon.com/en_US/help/topic/G201953020#royalties"

FEE_MODELS: dict[str, FeeModel] = {
    # ---------- verified (2026-11-09) ----------
    "etsy.us": FeeModel(
        ref="etsy.us", marketplace="Etsy", region="US", currency="USD",
        verified=True, listing_fee=0.20, transaction_pct=0.065, transaction_fixed=None,
        payment_pct=0.03, payment_fixed=0.25,
        source_url=_ETSY_US_URL, last_reviewed="2026-11-09",
        notes="US domestic USD orders; Offsite Ads 12/15% optional — see agents/fees/etsy.py"),
    "kdp.us": FeeModel(
        ref="kdp.us", marketplace="KDP", region="US", currency="USD",
        verified=True, listing_fee=None, transaction_pct=None, transaction_fixed=None,
        payment_pct=None, payment_fixed=None,   # royalty model, not a fee schedule
        source_url=_KDP_US_URL, last_reviewed="2026-11-09",
        notes="KDP paperback royalty 50/60% @ $9.99 threshold — see agents/fees/kdp.py"),
    # ---------- NOT verified — fee numbers intentionally absent ----------
    "etsy.eu": FeeModel(
        ref="etsy.eu", marketplace="Etsy", region="EU", currency="EUR",
        verified=False, listing_fee=None, transaction_pct=None, transaction_fixed=None,
        payment_pct=None, payment_fixed=None,
        source_url=None, last_reviewed=None, notes=_UNSET_NOTE),
    "etsy.global": FeeModel(
        ref="etsy.global", marketplace="Etsy", region="GLOBAL", currency="USD",
        verified=False, listing_fee=None, transaction_pct=None, transaction_fixed=None,
        payment_pct=None, payment_fixed=None,
        source_url=None, last_reviewed=None, notes=_UNSET_NOTE),
    "etsy.uk": FeeModel(
        ref="etsy.uk", marketplace="Etsy", region="UK", currency="GBP",
        verified=False, listing_fee=None, transaction_pct=None, transaction_fixed=None,
        payment_pct=None, payment_fixed=None,
        source_url=None, last_reviewed=None, notes=_UNSET_NOTE),
    "kdp.eu": FeeModel(
        ref="kdp.eu", marketplace="KDP", region="EU", currency="EUR",
        verified=False, listing_fee=None, transaction_pct=None, transaction_fixed=None,
        payment_pct=None, payment_fixed=None,
        source_url=None, last_reviewed=None, notes=_UNSET_NOTE),
    "kdp.global": FeeModel(
        ref="kdp.global", marketplace="KDP", region="GLOBAL", currency="USD",
        verified=False, listing_fee=None, transaction_pct=None, transaction_fixed=None,
        payment_pct=None, payment_fixed=None,
        source_url=None, last_reviewed=None, notes=_UNSET_NOTE),
}


class UnknownFeeModel(KeyError):
    """Raised when a fee_model_ref matches nothing — never silently default to US fees."""


def get_fee_model(ref: str) -> FeeModel:
    ref = (ref or "").strip().lower()
    if ref not in FEE_MODELS:
        raise UnknownFeeModel(f"unknown fee_model_ref '{ref}' — known: {sorted(FEE_MODELS)}")
    return FEE_MODELS[ref]


def unit_economics(ref: str, item_price: float, shipping: float = 0.0) -> dict[str, Any]:
    """Single calculation path. Unverified models return source='partial' and no numbers."""
    model = get_fee_model(ref)
    price = float(item_price)
    ship = max(0.0, float(shipping))
    if model.marketplace == "KDP":
        # royalty model — not a fee schedule; never report fee deductions for KDP
        return {
            "fee_model_ref": model.ref,
            "marketplace": "KDP",
            "region": model.region,
            "currency": model.currency,
            "verified": model.verified,
            "source": "live" if model.verified else "partial",
            "total_fees": None,
            "net_receipt": None,
            "item_price": price,
            "source_url": model.source_url,
            "last_reviewed": model.last_reviewed,
            "notes": model.notes,
        }
    if not model.verified:
        return {
            "fee_model_ref": model.ref,
            "marketplace": model.marketplace,
            "region": model.region,
            "currency": model.currency,
            "verified": False,
            "source": "partial",
            "total_fees": None,
            "net_receipt": None,
            "item_price": price,
            "source_url": None,
            "last_reviewed": None,
            "notes": model.notes,
        }
    listing = float(model.listing_fee or 0.0)
    tx = round((price + ship) * float(model.transaction_pct or 0.0), 2)
    pay = round(price * float(model.payment_pct or 0.0) + float(model.payment_fixed or 0.0), 2)
    total = round(listing + tx + pay, 2)
    return {
        "fee_model_ref": model.ref,
        "marketplace": model.marketplace,
        "region": model.region,
        "currency": model.currency,
        "verified": True,
        "source": "live",
        "listing_fee": listing,
        "transaction_fee": tx,
        "payment_processing_fee": pay,
        "total_fees": total,
        "net_receipt": round(price - total, 2),
        "item_price": price,
        "source_url": model.source_url,
        "last_reviewed": model.last_reviewed,
        "notes": model.notes,
    }
