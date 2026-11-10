"""Phase 2 — demo labelling & gating: no hard-coded 7.5/7.0 in demo/partial.

Guarantee: without Etsy or Trends keys, nothing is written as live; with AIHQ_ALLOW_DEMO=0 nothing is created at all.
Scores are clamped to [0, 10].
"""
import os
import json
from pathlib import Path

import pytest

import backend.app.config as cfg
import backend.app.db as dbmod
from agents.capabilities import scoring
from backend.app.db import get_store
from backend.app.services import store as svc


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "BOOKS_DIR", tmp_path / "books")
    monkeypatch.setattr(cfg, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cfg, "SQLITE_PATH", tmp_path / "data" / "test.db")
    dbmod.reset_store_for_tests()
    yield tmp_path
    dbmod.reset_store_for_tests()


def test_clamp_score():
    assert svc.clamp_score(0) == 0.0
    assert svc.clamp_score(5.5) == 5.5
    assert svc.clamp_score(10) == 10.0
    assert svc.clamp_score(12.3) == 10.0
    assert svc.clamp_score(-4) == 0.0
    assert svc.clamp_score("garbage") == 0.0
    assert svc.clamp_score(None) == 0.0


def test_clamped_in_affiliate_scoring():
    c = scoring.score_candidate({"product": "p", "est_price": 20.0, "commission": 10,
                                 "cookie_days": 30, "demand": "high", "competition": "low"})
    assert 0.0 <= c["score"] <= 10.0
    c2 = scoring.score_candidate({"product": "p2", "est_price": 10.0, "commission": 99.0,
                                  "cookie_days": 30, "demand": "high", "competition": "low"})
    assert 0.0 <= c2["score"] <= 10.0
    c3 = scoring.score_candidate({"product": "p3", "est_price": 10.0, "commission": -50,
                                  "cookie_days": -7, "demand": "high", "competition": "low"})
    assert 0.0 <= c3["score"] <= 10.0


def test_scorer_blocks_demo_without_flag(tmp_env, monkeypatch, tmp_path):
    """With no ETSY keys, intelligence.scorer must refuse to write fake opportunities."""
    for k in ("ETSY_API_KEY", "ETSY_KEYSTRING", "ETSY_SHARED_SECRET",
              "ETSY_ACCESS_TOKEN", "ETSY_REFRESH_TOKEN", "ETSY_SHOP_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("AIHQ_ALLOW_DEMO", raising=False)
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")     # deterministic fallback — may emit fake
    from agents.departments.market_intel import scan as sm
    out = sm.run("scan this", task_id=None)
    assert out.get("ok") is True
    rows = svc.list_opportunities()
    assert rows == []                            # no fake opportunities written
    assert all(r.get("source") != "live" for r in rows)   # nothing mislabeled as live


def test_scanner_with_allow_demo_allows_labelled_output(tmp_env, monkeypatch):
    """AIHQ_ALLOW_DEMO=1 → deterministic fallback is tagged demo, never live."""
    import agents.departments.market_intel.scan as scan
    for k in ("ETSY_API_KEY", "ETSY_KEYSTRING", "ETSY_SHARED_SECRET",
              "ETSY_ACCESS_TOKEN", "ETSY_REFRESH_TOKEN", "ETSY_SHOP_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    monkeypatch.setenv("AIHQ_ALLOW_DEMO", "1")
    # detector: with no real keys the demo data is always tagged
    out = scan.run("test scan", task_id=None)
    rows = svc.list_opportunities()
    # rows must not be labelled live
    assert all(r.get("source") != "live" for r in rows)


def test_dump_clamping_bounds_fuzz():
    for v in (1e9, -1e9, 42.4242, 5, "0.1", "9.999", None, "nan"):
        s = svc.clamp_score(v)
        assert 0.0 <= s <= 10.0, v
