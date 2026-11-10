"""اختبارات AI Business HQ — من الصفر: السجل، الـCEO، بوابة الموافقة، الحساب."""
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


# ---------------- السجل ----------------
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
    ("ارفع الكتاب على Etsy", "books.publishing"),
    ("ابحث عن فرصة تسويق بالعمولة", "affiliate"),
    ("احسب هامش كتاب بسعر 9.5 دولار", "finance"),
    ("افحص جودة الكتاب الحالي", "qa"),
    ("اقترح حزمة تسويق لكتاب", "marketing"),
])
def test_ceo_routes(task, expected):
    assert ceo.route_task(task) == expected


# ---------------- سير الكتاب الكامل ----------------
def test_books_pipeline_with_publish_gate(tmp_env):
    from agents.departments.books import content
    out = content.run(idea="سلحفاة تعشق الرسم", task_id=None, stop_after="story")
    assert out["ok"], out
    slug = out["slug"]

    build = content.build_existing(slug)
    assert build["ok"], build
    pdf = Path(build["pdf_path"])
    assert pdf.exists() and pdf.read_bytes()[:4] == b"%PDF"

    from agents.departments.qa import checker
    qa = checker.run(slug)
    assert qa["ok"] and qa["verdict"].startswith("PASS"), qa

    # بوابة الموافقة: لا نشر بلا موافقة
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(f"/api/books/{slug}/publish-request", json={"slug": slug, "note": "اختبار"},
                    headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"})
    assert r.status_code == 200
    aid = r.json()["approval_id"]

    # رفض مرفوض التنفيذ
    r = client.post(f"/api/approvals/{aid}/decide",
                    json={"decision": "reject", "note": "لاحقاً"},
                    headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"})
    assert r.status_code == 200
    assert svc.get_approval(aid)["status"] == "rejected"

    # طلب جديد ثم قبول — بلا ETSY_* لا يجوز التسمية "published"؛ يظهر خطأ حقيقي
    aid = client.post(f"/api/books/{slug}/publish-request",
                      json={"slug": slug, "note": "مرة أخرى"},
                      headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"}).json()["approval_id"]
    r = client.post(f"/api/approvals/{aid}/decide",
                    json={"decision": "approve", "note": "تم"},
                    headers={"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"})
    assert r.status_code in (502, 422), r.text
    book = svc.get_product(slug)
    assert book["status"] in ("story", "images", "pdf", "qa", "draft_failed"), book
    assert book["status"] != "published"


# ---------------- حساب حتمي للعمولة ----------------
def test_affiliate_scorer_deterministic():
    from agents.departments.affiliate.affiliate import score_candidate
    good = score_candidate({"product": "a", "est_price": 20.0, "commission": 10.0,
                            "cookie_days": 30, "demand": "rising", "competition": "low"})
    bad = score_candidate({"product": "b", "est_price": 5.0, "commission": 1.0,
                           "cookie_days": 3, "demand": "low", "competition": "high"})
    assert good["unit_commission"] == 2.0
    assert good["score"] > bad["score"]
    assert len(bad["risks"]) == 3


# ---------------- المالية حتمية ----------------
def test_finance_math_is_python():
    from agents.departments.finance.calculator import unit_economics
    fin = unit_economics(9.5, 24)
    expect = 9.5 - (0.20 + 9.5 * (0.065 + 0.03))
    assert abs(fin["etsy"]["net_before_ads"] - round(expect, 2)) < 0.001
    assert abs(fin["kdp_paperback"]["royalty_60_pct"] - round(9.5 * 0.60, 2)) < 0.001


# ---------------- API حارس ----------------
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
    """/api/agents و /api/capabilities و /api/observability — 401 بلا رمز وبيانات معه."""
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
    assert len(agents) >= 20          # 10 أقسام × 2-4 وكلاء
    assert len(caps) >= 8
    assert {a["department_key"] for a in agents} >= {"finance", "affiliate", "qa"}
    assert {c["id"] for c in caps} >= {"unit_economics", "web_research", "qa_checks"}

    # تشغيل تدفق حتمي عبر الـ API (ينشئ task قبل تنفيذ القسم) ثم التحقق من المراقبة
    out = client.post("/api/departments/finance/run",
                      json={"task": "book 9.99 usd 24 pages"}, headers=headers)
    assert out.status_code == 200, out.text
    assert out.json()["ok"]
    obs = client.get("/api/observability", headers=headers).json()
    assert obs["counts"]["tasks"] >= 1
    assert any(d["domain"] == "finance" for d in obs["tasks_by_domain"])
    assert obs["executions_by_agent"]
    assert "approvals" in obs and "tokens_total" in obs
