"""Amazon KDP paperback fees / royalties — verified 2026-11-09.

Sources:
  - Printing cost formulae per territory (US B&W 24-page min): $2.15 for 24–108 pages,
    $2.15 + $0.012 every page above 108.
    https://kdp.amazon.com/en_US/help/topic/G201953020#printing-cost-table
  - Royalty split: 60% for prices ≥ $9.99, 50% below.
    https://kdp.amazon.com/en_US/help/topic/G201953020#royalties
  - Delivery cost per MB for eBooks (35% royalty tier only): $0.15/MB
    https://kdp.amazon.com/en_US/help/topic/G201953020#5-savings
"""
from __future__ import annotations

SOURCE_URL_PRINTING = "https://kdp.amazon.com/en_US/help/topic/G201953020#printing-cost-table"
SOURCE_URL_ROYALTY = "https://kdp.amazon.com/en_US/help/topic/G201953020#royalties"
SOURCE_URL_DELIVERY = "https://kdp.amazon.com/en_US/help/topic/G201953020#5-savings"
LAST_REVIEWED = "2026-11-09"

# US black-ink paperback, standard trim (white paper)
# Formula scales from 24 pages
PAPERBACK_ROYALTY_HIGH = 0.60
PAPERBACK_ROYALTY_LOW = 0.50
PAPERBACK_ROYALTY_THRESHOLD = 9.99
PRINT_MIN_PAGES = 24
PRINT_FIRST_TIER_CAP = 108
PRINT_COST_TIER1_USD = 2.15            # ≤108 pages
PRINT_PER_PAGE_USD = 0.012              # every page above 108
EBOOK_DELIVERY_PER_MB = 0.15


def printing_cost(pages: int) -> float:
    """US B&W paperback, standard trim. Honor page count exactly."""
    p = max(int(pages or 0), PRINT_MIN_PAGES)
    if p <= PRINT_FIRST_TIER_CAP:
        return PRINT_COST_TIER1_USD
    return round(PRINT_COST_TIER1_USD + (p - PRINT_FIRST_TIER_CAP) * PRINT_PER_PAGE_USD, 2)


def royalty_rate(list_price: float) -> float:
    return PAPERBACK_ROYALTY_HIGH if float(list_price) >= PAPERBACK_ROYALTY_THRESHOLD else PAPERBACK_ROYALTY_LOW


def paperback_royalty(list_price: float, pages: int) -> dict[str, float]:
    p = max(int(pages or 0), PRINT_MIN_PAGES)
    rate = royalty_rate(list_price)
    royalty = round(float(list_price) * rate - printing_cost(p), 2)
    return {
        "pages": p,
        "list_price": float(list_price),
        "royalty_rate": rate,
        "printing_cost": printing_cost(p),
        "royalty_usd": royalty,
        "marketplace": "US",
        "ink_type": "black-white",
        "source_url": SOURCE_URL_ROYALTY,
        "last_reviewed": LAST_REVIEWED,
    }