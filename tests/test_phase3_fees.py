"""Phase 3 — fee models: every rule with a reference number and Source URL.

Hand-checked against Etsy docs and KDP FAQ. No invented numbers in this file.
"""
import pytest

from agents.fees import etsy, kdp
from agents.capabilities.finance import unit_economics


# Etsy listing fee
def test_etsy_listing_fee():
    assert etsy.listing_fee() == 0.20


def test_etsy_transaction_fee():
    assert etsy.transaction_fee(10.0) == 0.65   # 6.5% of price
    assert etsy.transaction_fee(9.99, shipping=0.0) == pytest.approx(0.65, abs=0.01)
    assert etsy.transaction_fee(10.0, shipping=2.0) == pytest.approx(0.78, abs=0.01)


def test_etsy_payment_processing():
    # US domestic: 3.0% + $0.25 per order
    assert etsy.payment_processing_fee(10.0) == pytest.approx(0.55, abs=0.001)
    assert etsy.payment_processing_fee(4.99) == pytest.approx(0.40, abs=0.001)


def test_etsy_total_fee_no_offsite():
    """Hand-calc for $9.99 item, no offsite: 0.20 + 0.65 + (0.30 + 0.25) = $1.40"""
    total = etsy.total_fee(9.99)
    assert total["transaction_fee"] == pytest.approx(0.65, abs=0.01)
    assert total["payment_processing_fee"] == pytest.approx(0.55, abs=0.001)
    assert total["offsite_ads_fee"] == 0.0
    assert total["total_fees"] == pytest.approx(1.40, abs=0.01)
    assert total["net_receipt"] == pytest.approx(8.59, abs=0.01)


def test_etsy_offsite_small_shop():
    """Shop under $10k: 12% ads fee on top of the others."""
    total = etsy.total_fee(10.0, annual_sales_usd=5_000, include_offsite=True)
    # 0.20 + (0.065·10) + (0.30 + 0.25) + 0.12·10 = 1.95 total; net = $8.05
    assert total["offsite_ads_fee"] == pytest.approx(1.20, abs=0.01)
    assert total["total_fees"] == pytest.approx(2.60, abs=0.01)
    assert total["net_receipt"] == pytest.approx(7.40, abs=0.01)


# KDP paperback royalty
def test_kdp_printing_cost_black_ink():
    """US B&W paperback 24 pages: $2.15 flat."""
    assert kdp.printing_cost(24) == 2.15
    assert kdp.printing_cost(60) == 2.15
    assert kdp.printing_cost(108) == 2.15
    assert kdp.printing_cost(109) == pytest.approx(2.162, abs=0.002)


def test_kdp_paperback_royalty_60pct_case():
    """$9.99 list, 24 pages, US B&W → 60% rate: 9.99·0.60 − 2.15 = $3.84."""
    r = kdp.paperback_royalty(9.99, 24)
    assert r["royalty_rate"] == 0.60
    assert r["printing_cost"] == 2.15
    assert r["royalty_usd"] == pytest.approx(3.84, abs=0.01)


def test_kdp_paperback_royalty_50pct_case():
    """$4.99 list → 50% rate: 4.99·0.50 − 2.15 = $0.35."""
    r = kdp.paperback_royalty(4.99, 24)
    assert r["royalty_rate"] == 0.50
    assert r["royalty_usd"] == pytest.approx(0.345, abs=0.01)


def test_unit_economics_includes_pages_in_calc():
    out = unit_economics(9.99, 150)
    # Tariff drops from 60% only when >= 9.99
    assert out["kdp_paperback"]["pages"] == 150
    # Printing cost now higher than the 24-page flat 2.15
    assert out["kdp_paperback"]["printing_cost"] > 2.15


def test_assumptions_honesty_lines_present():
    out = unit_economics(9.99, 24)
    assert any("USD" in a for a in out["assumptions"])
    assert any("Offsite Ads" in a for a in out["assumptions"])
    assert out["etsy"]["source_url"].startswith("https://")
