"""اختبارات خط الأنابيب كاملة في وضع المحاكاة — بلا شبكة وبلا مفاتيح."""
import json
from pathlib import Path

import pytest

import kidbook.db as dbmod
from kidbook import config, engine


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOOKS_DIR", tmp_path / "books")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "SQLITE_PATH", tmp_path / "data" / "kidbook.db")
    dbmod._store = None
    yield tmp_path
    dbmod._store = None


def test_market_report(tmp_env):
    out = engine.analyze_market()
    assert out["ok"], out
    rp = Path(out["report_path"])
    assert rp.exists()
    assert "تقرير" in rp.read_text(encoding="utf-8")


def test_story_then_build_pdf(tmp_env):
    out = engine.create_story("أرنب صغير يتعلم المشاركة")
    assert out["ok"], out
    slug = out["slug"]
    story_path = Path(out["story_path"])
    story = json.loads(story_path.read_text(encoding="utf-8"))
    assert len(story["pages"]) == config.PAGES
    assert story["title"]

    built = engine.build_book(slug)
    assert built["ok"], built
    pdf = Path(built["pdf_path"])
    assert pdf.exists()
    assert pdf.read_bytes()[:4] == b"%PDF"
    assert pdf.stat().st_size > 10_000
    # الصور تولّدت لكل الصفحات
    imgs = sorted((tmp_env / "books" / slug).glob("p*.png"))
    assert len(imgs) == config.PAGES


def test_publish_requires_human_confirmation(tmp_env):
    out = engine.create_story("سلحفاة تعشق الرسم")
    assert engine.build_book(out["slug"])["ok"]

    denied = engine.publish_book(out["slug"], human_confirmed=False)
    assert not denied["ok"]

    allowed = engine.publish_book(out["slug"], human_confirmed=True)
    assert allowed["ok"], allowed
    assert str(allowed["listing_id"]).startswith("MOCK-")
    assert allowed["mock"] is True


def test_orchestrator_routing():
    assert engine.route_task("حلّل السوق من فضلك") == "kids_books.market"
    assert engine.route_task("plot the etsy trend now") == "kids_books.market"
    assert engine.route_task("ارفع الكتاب على Etsy") == "kids_books.publishing"
    assert engine.route_task("اكتب قصة عن قطّة تطير") == "kids_books.content"


def test_story_validation_rejects_bad_model_output():
    from kidbook import tools
    with pytest.raises(ValueError):
        tools.validate_story({"title": "x"}, 12)   # حقول ناقصة
    good = tools.validate_story(
        {"title": "t", "character_sheet": "c", "style": "s",
         "pages": [{"text": f"نص {i}", "image_prompt": f"scene {i}"} for i in range(1, 13)],
         "etsy": {"title": "t", "description": "d", "tags": ["a"] * 20}}, 12)
    assert len(good["etsy"]["tags"]) == 13  # الوسوم تُقتطع إلى 13
