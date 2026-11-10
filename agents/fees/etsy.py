"""Etsy fees — verified 2026-11-09.

Etsy (United States marketplace, USD):
  - Listing fee: $0.20 per listing item (paid on creation, valid 4 months or until sold)
    https://help.etsy.com/hc/en-us/articles/115015617766-What-are-the-fees-and-payments-on-Etsy-
  - Transaction fee: 6.5% of (item price × quantity + shipping/gift wrap), charged on sale
    https://help.etsy.com/hc/en-us/articles/115015617766-What-are-the-fees-and-payments-on-Etsy-
  - Payment processing (US): 3.0% + $0.25 per order (domestic USD orders)
    https://help.etsy.com/hc/en-us/articles/360002634974-Payment-expense-account-and-related-fees
  - Offsite Ads: optional. 12% for eligible shops (under $10k sales/year), 15% for all others.
    https://help.etsy.com/hc/en-us/articles/360000616694-How-do-Etsy-Offsite-Ads-work-
"""
from __future__ import annotations

SOURCE_URL = "https://help.etsy.com/hc/en-us/articles/115015617766-What-are-the-fees-and-payments-on-Etsy-"
SOURCE_URL_PAYMENTS = "https://help.etsy.com/hc/en-us/articles/360002634974-Payment-expense-account-and-related-fees"
SOURCE_URL_OFFSITE = "https://help.etsy.com/hc/en-us/articles/360000616694-How-do-Etsy-Offsite-Ads-work-"
LAST_REVIEWED = "2026-11-09"

# US, domestic USD orders (the common case for a new shop)
LISTING_FEE_USD = 0.20
TRANSACTION_PCT = 0.065
PAYMENT_PCT = 0.03
PAYMENT_FIXED_USD = 0.25
OFFSITE_ADS_PCT_SMALL = 0.12     # shops under $10k annual sales
OFFSITE_ADS_PCT_LARGE = 0.15     # all other shops (eligible for 15%)


def listing_fee() -> float:
    return LISTING_FEE_USD


def transaction_fee(item_price: float, shipping: float = 0.0) -> float:
    return round((float(item_price) + max(0.0, float(shipping))) * TRANSACTION_PCT, 2)


def payment_processing_fee(item_price: float) -> float:
    """US domestic USD order — 3.0% + $0.25 fixed per order."""
    return round(float(item_price) * PAYMENT_PCT + PAYMENT_FIXED_USD, 2)


def offsite_ads_fee(item_price: float, annual_sales_usd: float) -> float | None:
    """Returns the fee if Offsite Ads eligible, otherwise None."""
    if annual_sales_usd < 10_000:
        return round(float(item_price) * OFFSITE_ADS_PCT_SMALL, 2)
    return round(float(item_price) * OFFSITE_ADS_PCT_LARGE, 2)


def total_fee(item_price: float, shipping: float = 0.0,
              annual_sales_usd: float | None = None,
              include_offsite: bool = False) -> dict[str, float]:
    """Full fee breakdown for a single completed order."""
    tx = transaction_fee(item_price, shipping)
    pay = payment_processing_fee(item_price)
    ads = offsite_ads_fee(item_price, float(annual_sales_usd or 0)) if include_offsite else 0.0
    total = round(LISTING_FEE_USD + tx + pay + (ads or 0.0), 2)
    net = round(float(item_price) - total, 2)
    return {
        "listing_fee": LISTING_FEE_USD,
        "transaction_fee": tx,
        "payment_processing_fee": pay,
        "offsite_ads_fee": ads or 0.0,
        "total_fees": total,
        "net_receipt": net,
        "currency": "USD",
        "marketplace": "US",
        "source_url": SOURCE_URL,
        "last_reviewed": LAST_REVIEWED,
    }
