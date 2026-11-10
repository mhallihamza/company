"""Item 7 — per-market fee registry + language adapters + engine profile pass-in.

Honest-number rules:
  * etsy.us → VERIFIED (2026-11-09, source_url). Switching to etsy.eu must yield partial, never guessed fees.
  * Unverified regions: unit_economics returns total_fees=None, source='partial'.
  * Arabic profile → RTL; disabled profiles are skipped by the engine.
"""
import json

import pytest

import backend.app.config as cfg
import backend.app.db as dbmod


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "BOOKS_DIR", tmp_path / "books")
    monkeypatch.setattr(cfg, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cfg, "SQLITE_PATH", tmp_path / "data" / "test.db")
    monkeypatch.setattr(cfg, "DB_BACKEND", "sqlite")
    monkeypatch.setattr(cfg, "DATABASE_URL", "")
    dbmod.reset_store_for_tests()
    yield tmp_path
    dbmod.reset_store_for_tests()


# ---------- fee registry ----------

def test_etsy_us_verified_and_eu_not():
    from agents.fees.registry import FEE_MODELS
    us = FEE_MODELS["etsy.us"]
    eu = FEE_MODELS["etsy.eu"]
    assert us.verified is True
    assert us.source_url and us.last_reviewed == "2026-11-09"
    assert eu.verified is False
    assert eu.listing_fee is None and eu.payment_fixed is None
    assert eu.source_url is None


def test_unknown_fee_model_raises():
    from agents.fees.registry import get_fee_model, UnknownFeeModel
    with pytest.raises(UnknownFeeModel):
        get_fee_model("etsy.mars")


def test_unit_economics_us_matches_hand_calc():
    from agents.fees.registry import unit_economics
    out = unit_economics("etsy.us", 9.99)
    # listing 0.20 + tx round(9.99*0.065, 2)=0.65 + payment round(9.99*0.03+0.25, 2)=0.55 → 1.40
    assert out["verified"] is True
    assert out["source"] == "live"
    assert out["total_fees"] == 1.40
    assert out["net_receipt"] == 8.59


def test_switching_profile_changes_fee_result():
    from agents.fees.registry import unit_economics
    us = unit_economics("etsy.us", 9.99)
    eu = unit_economics("etsy.eu", 9.99)
    assert us["source"] == "live" and us["total_fees"] is not None
    assert eu["source"] == "partial"
    assert eu["total_fees"] is None and eu["net_receipt"] is None


def test_kdp_model_never_reports_fee_deductions():
    from agents.fees.registry import unit_economics
    out = unit_economics("kdp.us", 9.99)
    assert out["verified"] is True
    assert out["total_fees"] is None   # royalty model — not fee-based


# ---------- localization ----------

def test_arabic_profile_is_rtl():
    from agents.localization import get_language_profile, font_path_for
    profile = get_language_profile("ar")
    assert profile.text_direction == "rtl"
    assert profile.qa_ruleset_ref == "qa.ar"
    assert font_path_for("font.amiri").exists()


def test_fr_and_en_are_ltr_with_latin_font():
    from agents.localization import get_language_profile, font_path_for
    for code in ("en", "fr"):
        profile = get_language_profile(code)
        assert profile.text_direction == "ltr"
        assert font_path_for(profile.font_ref).exists()


def test_story_prompts_are_language_native():
    from agents.localization import get_story_prompt
    assert "Arabic" in get_story_prompt("ar", "idea", 12) or "بالعربية" in get_story_prompt("ar", "idea", 12)
    assert "française" in get_story_prompt("fr", "idée", 12).lower() or "enfants" in get_story_prompt("fr", "idée", 12)
    assert "English" in get_story_prompt("en", "idea", 12)


def test_unknown_language_fails_fast():
    from agents.localization import get_language_profile, UnsupportedLanguage
    with pytest.raises(UnsupportedLanguage):
        get_language_profile("de")


# ---------- profiles seeding + engine ----------

def test_seed_produces_new_columns(tmp_env):
    from backend.app.routers.profiles import seed
    seed()
    from backend.app.db import get_store
    s = get_store()
    rows = s.q("SELECT * FROM market_profiles ORDER BY country")
    by_key = {(r["country"], r["language"]): r for r in rows}
    us = by_key[("US", "en")]
    assert us["fee_model_ref"] == "etsy.us"
    assert us["story_prompt_ref"] == "story.en"
    assert us["font_ref"] == "font.dejavu"
    assert us["text_direction"] == "ltr"
    assert us["qa_ruleset_ref"] == "qa.en"
    cal = json.loads(us["seasonal_calendar"])
    assert all("lead_weeks" in ev for ev in cal)
    assert any(ev["name"] == "back_to_school" for ev in cal)
    sa = by_key[("SA", "ar")]
    assert sa["text_direction"] == "rtl" and sa["fee_model_ref"] == "etsy.global"


def test_list_profiles_exposes_fee_badge(tmp_env, monkeypatch):
    monkeypatch.setenv("FOUNDER_TOKEN", "test-founder-token")
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    r = client.get("/api/profiles",
                   headers={"Authorization": "Bearer test-founder-token"})
    assert r.status_code == 200
    rows = {(x["country"], x["language"]): x for x in r.json()}
    assert rows[("US", "en")]["fee_verified"] is True
    assert rows[("FR", "fr")]["fee_verified"] is False
    assert rows[("SA", "ar")]["fee_verified"] is False


def test_engine_skips_disabled_market(tmp_env, monkeypatch):
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    monkeypatch.setenv("AIHQ_ALLOW_DEMO", "1")
    from backend.app.routers.profiles import seed
    from backend.app.db import get_store
    seed()
    s = get_store()
    s._execute("UPDATE market_profiles SET enabled = 0 WHERE country='FR' AND language='fr'")
    from agents.workflows.opportunity_engine import run as run_engine
    out = run_engine("cahier activités", market="fr-fr")
    assert out["ok"] is False
    assert "disabled" in out["error"] or "no enabled market profile" in out["error"]
    out_us = run_engine("back to school niches", market="us-en")
    assert out_us["ok"] is True
    assert out_us.get("market") == "us-en"


def test_engine_unknown_market_fails_fast(tmp_env, monkeypatch):
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    from agents.workflows.opportunity_engine import run as run_engine
    out = run_engine("x", market="mars-zz")
    assert out["ok"] is False
    assert "no enabled market profile" in out["error"]


def test_qa_arabic_rules_wired():
    from agents.capabilities.qa import check_product
    from agents.localization import QA_RULES
    assert QA_RULES["ar"] and QA_RULES["fr"]
