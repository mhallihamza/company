"""اختبارات أقسام AI Business HQ: الذكاء، التسويق بالعمولة، التسويق، المالية، الجودة، والموافقات."""
from pathlib import Path

import pytest

import kidbook.db as dbmod
from kidbook import config, engine
from kidbook.db import get_store
from kidbook.domains import DOMAIN_REGISTRY
from kidbook.domains.affiliate import score_candidate
from kidbook.domains.finance import unit_economics


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOOKS_DIR", tmp_path / "books")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "SQLITE_PATH", tmp_path / "data" / "kidbook.db")
    dbmod._store = None
    yield tmp_path
    dbmod._store = None


# ---------------- سجل الأقسام ----------------
def test_registry_has_all_departments():
    expected = {"kids_books.market", "kids_books.content", "kids_books.publishing",
                "intelligence", "affiliate", "marketing", "finance", "qa"}
    assert expected.issubset(set(DOMAIN_REGISTRY.keys()))
    for spec in DOMAIN_REGISTRY.values():
        assert spec.keywords, f"القسم {spec.key} بلا كلمات توجيه"
        assert spec.approval_policy


# ---------------- ذكاء السوق ----------------
def test_intelligence_saves_opportunities(tmp_env):
    out = engine.run_intelligence("فرص كتب الأطفال هذه الأسبوع")
    assert out["ok"], out.get("error")
    assert Path(out["report_path"]).exists()
    opps = get_store().list_opportunities(sector="intelligence")
    assert opps, "لم تُسجَّل فرص"
    assert all(o["score"] is not None for o in opps)


# ---------------- التسويق بالعمولة ----------------
def test_affiliate_scorer_is_deterministic():
    c = score_candidate({"product": "x", "est_price": 20.0, "commission": 10,
                         "cookie_days": 30, "demand": "rising", "competition": "low"})
    assert c["unit_commission"] == 2.0
    assert c["score"] > 8.0 and not c["risks"]

    risky = score_candidate({"product": "y", "est_price": 10.0, "commission": 2,
                             "cookie_days": 5, "demand": "low", "competition": "high"})
    assert len(risky["risks"]) == 3
    assert risky["score"] < c["score"]


def test_affiliate_department_saves_ranked_opps(tmp_env):
    out = engine.run_affiliate("منتجات مكملة لكتب الأطفال")
    assert out["ok"], out.get("error")
    opps = get_store().list_opportunities(sector="affiliate")
    assert len(opps) >= 3
    scores = [o["score"] for o in reversed(opps)]   # إدراجها مرتبةً تصاعدياً بالid، أعرضها بالأحدث أولاً
    assert scores == sorted(scores, reverse=True)   # الأعلى أولاً


# ---------------- التسويق ----------------
def test_marketing_pack_created(tmp_env):
    out = engine.run_marketing("كتاب قصص عربية للأطفال 3-6")
    assert out["ok"], out.get("error")
    pack = Path(out["marketing_pack"])
    assert pack.exists()
    text = pack.read_text(encoding="utf-8")
    assert "SEO" in text and "Pinterest" in text


# ---------------- المالية (حتمية) ----------------
def test_finance_unit_economics_deterministic():
    fin = unit_economics(9.5, 24)
    etsy_net = 9.5 - (0.20 + 9.5 * (0.065 + 0.03))
    assert abs(fin["etsy"]["net_before_ads"] - round(etsy_net, 2)) < 0.001
    assert abs(fin["kdp_paperback"]["royalty_60_pct"] - round(9.5 * 0.60, 2)) < 0.001


def test_finance_department(tmp_env):
    out = engine.run_finance("book 9.5 usd 24 pages")
    assert out["ok"], out.get("error")
    assert Path(out["report_path"]).exists()


# ---------------- الجودة ----------------
def test_qa_passes_valid_book(tmp_env):
    story = engine.create_story("دبدوب يفقد حذاءه")
    assert story["ok"], story
    assert engine.build_book(story["slug"])["ok"]
    q = engine.run_qa(story["slug"])
    assert q["ok"], q.get("error")
    assert q["verdict"].startswith("PASS"), q.get("qa_report")


# ---------------- بوابة الموافقات ----------------
def test_publish_approval_flow(tmp_env):
    story = engine.create_story("سنونو يتعلّم الطيران")
    engine.build_book(story["slug"])
    slug = story["slug"]

    req = engine.request_publish(slug, "طلب عادي")
    assert req["ok"] and req["status"] == "pending"
    pending = [a for a in get_store().list_approvals(status="pending") if a["ref"] == slug]
    assert pending

    denied = engine.publish_book(slug, human_confirmed=False)
    assert not denied["ok"]

    approved = engine.decide_publish(req["approval_id"], "approve", "تم")
    assert approved["ok"], approved
    assert str(approved["listing_id"]).startswith("MOCK-")
    assert get_store().get_approval(req["approval_id"])["status"] == "approved"

    req2 = engine.request_publish(slug, "طلب ثانٍ")
    rejected = engine.decide_publish(req2["approval_id"], "reject", "لست جاهزاً")
    assert rejected["ok"] and rejected["decision"] == "rejected"
    assert get_store().get_approval(req2["approval_id"])["status"] == "rejected"
