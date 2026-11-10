"""AI Business HQ tests — from scratch: registry, CEO, approval gate, accounting."""
import json
import os
from pathlib import Path

import pytest

import backend.app.config as cfg
import backend.app.db as dbmod
from agents import registry
from agents.ceo import graph as ceo
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


# ---------------- registry ----------------
def test_registry_lists_required_departments():
    keys = {d.key for d in registry.list_departments()}
    expected = {"books.market", "books.content", "books.publishing", "intelligence",
                "affiliate", "marketing", "finance", "qa", "product", "design"}
    assert expected.issubset(keys)
    for d in registry.list_departments():
        assert d.to_public()["approval_policy"]
        assert d.allowed_tools and d.capabilities


# ---------------- CEO router ----------------
@pytest.mark.parametrize("task,expected", [
    ("upload the book on Etsy", "books.publishing"),
    ("search for affiliate opportunity", "affiliate"),
    ("calculate the margin of a 9.5 dollar book", "finance"),
    ("run QA on the current book", "qa"),
    ("suggest a marketing pack for a book", "marketing"),
])
def test_ceo_routes(task, expected):
    assert ceo.route_task(task) == expected


# ---------------- full book pipeline ----------------
def test_books_pipeline_with_publish_gate(tmp_env):
    from agents.departments.books import content
    out = content.run(idea="a turtle who loves to draw", task_id=None, stop_after="story")
    assert out["ok"], out
    slug = out["slug"]

    build = content.build_existing(slug)
    assert build["ok"], build
    pdf = Path(build["pdf_path"])
    assert pdf.exists() and pdf.read_bytes()[:4] == b"%PDF"

    from agents.departments.qa import checker
    qa = checker.run(slug)
    assert qa["ok"] and qa["verdict"].startswith("PASS"), qa

    # approval gate: no publishing without approval
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(f"/api/books/{slug}/publish-request", json={"slug": slug, "note": "asap"},
                    headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"})
    assert r.status_code == 200
    aid = r.json()["approval_id"]

    # rejected decision — execution is refused
    r = client.post(f"/api/approvals/{aid}/decide",
                    json={"decision": "reject", "note": "later"},
                    headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"})
    assert r.status_code == 200
    assert svc.get_approval(aid)["status"] == "rejected"

    # fresh request then approve — without ETSY_* it must not be labelled "published"; a real error surfaces
    aid = client.post(f"/api/books/{slug}/publish-request",
                      json={"slug": slug, "note": "again"},
                      headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"}).json()["approval_id"]
    r = client.post(f"/api/approvals/{aid}/decide",
                    json={"decision": "approve", "note": "ok"},
                    headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"})
    assert r.status_code in (502, 422), r.text
    book = svc.get_product(slug)
    assert book["status"] in ("story", "images", "pdf", "qa", "draft_failed"), book
    assert book["status"] != "published"


# ---------------- deterministic commission math ----------------
def test_affiliate_scorer_deterministic():
    from agents.departments.affiliate.affiliate import score_candidate
    good = score_candidate({"product": "a", "est_price": 20.0, "commission": 10.0,
                            "cookie_days": 30, "demand": "rising", "competition": "low"})
    bad = score_candidate({"product": "b", "est_price": 5.0, "commission": 1.0,
                           "cookie_days": 3, "demand": "low", "competition": "high"})
    assert good["unit_commission"] == 2.0
    assert good["score"] > bad["score"]
    assert len(bad["risks"]) == 3


# ---------------- finance is deterministic ----------------
def test_finance_math_is_python():
    from agents.fees import etsy, kdp
    etsy_total = etsy.total_fee(9.5)
    expect = 9.5 - (0.20 + 9.5 * (0.065 + 0.03) + 0.25)   # listing + tx + 3% + $0.25
    assert abs(etsy_total["net_receipt"] - round(expect, 2)) < 0.001
    kdp_high = kdp.paperback_royalty(9.99, 24)             # ≥ $9.99 → 60% rate
    assert abs(kdp_high["royalty_usd"] - round(9.99 * 0.60 - 2.15, 2)) < 0.001


# ---------------- API guard ----------------
def test_api_auth_guard(tmp_env):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/api/departments")
    assert r.status_code == 401
    r = client.get("/api/departments",
                   headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401
    r = client.get("/api/departments",
                   headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"})
    assert r.status_code == 200
    assert len(r.json()) >= 10
    r = client.get("/api/health")
    assert r.status_code == 200


def test_hq_routes_and_observability(tmp_env):
    """/api/agents, /api/capabilities and /api/observability — 401 without a token, and data with one."""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"}

    for path in ("/api/agents", "/api/capabilities", "/api/observability"):
        assert client.get(path).status_code == 401
        r = client.get(path, headers=headers)
        assert r.status_code == 200, path

    agents = client.get("/api/agents", headers=headers).json()
    caps = client.get("/api/capabilities", headers=headers).json()
    assert len(agents) >= 20          # 10 departments x 2-4 agents
    assert len(caps) >= 8
    assert {a["department_key"] for a in agents} >= {"finance", "affiliate", "qa"}
    assert {c["id"] for c in caps} >= {"unit_economics", "web_research", "qa_checks"}

    # run a deterministic flow through the API (creates a task before the department runs), then verify observability
    out = client.post("/api/departments/finance/run",
                      json={"task": "book 9.99 usd 24 pages"}, headers=headers)
    assert out.status_code == 200, out.text
    assert out.json()["ok"]
    obs = client.get("/api/observability", headers=headers).json()
    assert obs["counts"]["tasks"] >= 1
    assert any(d["domain"] == "finance" for d in obs["tasks_by_domain"])
    assert obs["executions_by_agent"]
    assert "approvals" in obs and "tokens_total" in obs
