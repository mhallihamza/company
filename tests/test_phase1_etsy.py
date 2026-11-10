"""Phase 1 — Etsy truthfulness: no mock, no published without a real listing_id.

Tests cover:
- Etsy OAuth refresh (expired → refresh → retry)
- x-api-key in keystring:shared_secret format
- 4xx / 5xx fail loud, never mock
- publishing department never sets status `published` for real Etsy failures
"""
import json
import os
import sys
from pathlib import Path

import pytest

import backend.app.config as cfg
import backend.app.db as dbmod
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


class StubResp:
    def __init__(self, status_code: int, body: dict | None = None, text: str | None = None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text if text is not None else json.dumps(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            import requests
            resp = requests.Response()
            resp.status_code = self.status_code
            resp._content = self.text.encode("utf-8")
            resp.url = "https://fake.etsy/"
            raise requests.HTTPError(f"HTTP {self.status_code}", response=resp)


def _make_cfg():
    os.environ["ETSY_KEYSTRING"] = "TEST_KEYSTRING"
    os.environ["ETSY_SHARED_SECRET"] = "TEST_SHARED_SECRET"
    os.environ["ETSY_REFRESH_TOKEN"] = "TEST_REFRESH"
    os.environ["ETSY_SHOP_ID"] = "12345"
    os.environ["ETSY_TAXONOMY_ID"] = "116"


def _clear_cfg():
    for k in ("ETSY_KEYSTRING", "ETSY_SHARED_SECRET", "ETSY_REFRESH_TOKEN",
              "ETSY_SHOP_ID", "ETSY_TAXONOMY_ID", "ETSY_API_KEY", "ETSY_ACCESS_TOKEN"):
        os.environ.pop(k, None)


# ---------- unit: real HTTP flow with stubbed requests ----------
def test_x_api_key_format(monkeypatch, tmp_path):
    _make_cfg()
    pdf = tmp_path / "demo.pdf"; pdf.write_bytes(b"%PDF-1.7 hi")
    from agents.capabilities import marketplace as m
    captured = {}

    class StubReq:
        @staticmethod
        def request(method, url, **kwargs):
            captured["headers"] = kwargs.get("headers", {})
            captured["url"] = url
            return StubResp(200, {"listing_id": "42", "results": [], "count": 0})

    monkeypatch.setattr("requests.request", StubReq.request)
    body = m.requests_call_etsy("GET", "/listings/active", m._read_env(),
                                params={"keywords": "dinosaurs", "limit": 1}, timeout=5)
    assert captured["headers"]["x-api-key"] == "TEST_KEYSTRING:TEST_SHARED_SECRET"
    assert body.get("listing_id") == "42"


def test_refresh_then_retry_on_401(monkeypatch, tmp_path):
    _make_cfg()
    pdf = tmp_path / "demo.pdf"; pdf.write_bytes(b"%PDF-1.7 hi")
    from agents.capabilities import marketplace as m

    calls = {"listing": 0, "refresh": 0}

    def fake_request(method, url, **kwargs):
        if "listings" in url and method == "POST" and "/files" not in url and "/images" not in url:
            calls["listing"] += 1
            if calls["listing"] == 1:
                return StubResp(401, {"error": "invalid_token"})
            return StubResp(200, {"listing_id": "88"})
        if "listings" in url and "/files" in url:
            return StubResp(200, {})
        if "listings" in url and "/images" in url:
            return StubResp(200, {})
        return StubResp(200, {})

    def fake_post(url, **kwargs):
        calls["refresh"] += 1
        return StubResp(200, {"access_token": "NEW_ACCESS", "expires_in": 3600})

    monkeypatch.setattr("requests.request", fake_request)
    monkeypatch.setattr("requests.post", fake_post)

    result = m.etsy_create_draft({"title": "Dino", "description": "coloring",
                                   "tags": ["kids"]}, str(pdf), None, price=4.99)
    assert result["ok"] is True
    assert result["listing_id"] == "88"
    assert calls["listing"] == 2          # original + after 401 refresh retry
    assert calls["refresh"] >= 1          # refresh token endpoint hit


def test_5xx_raises_etsy_error(monkeypatch, tmp_path):
    _make_cfg()
    pdf = tmp_path / "demo.pdf"; pdf.write_bytes(b"%PDF-1.7 hi")
    from agents.capabilities import marketplace as m

    def always_500(method, url, **kwargs):
        return StubResp(500, {"error": "boom"})

    monkeypatch.setattr("requests.request", always_500)
    monkeypatch.setattr("requests.post", lambda url, **kwargs: StubResp(200, {"access_token": "X", "expires_in": 3600}))

    with pytest.raises(m.EtsyError) as exc_info:
        m.etsy_create_draft({"title": "Dino"}, str(pdf), None, price=4.99)
    assert exc_info.value.status_code == 500


def test_4xx_raises_etsy_error(monkeypatch, tmp_path):
    _make_cfg()
    pdf = tmp_path / "demo.pdf"; pdf.write_bytes(b"%PDF-1.7 hi")
    from agents.capabilities import marketplace as m

    def always_400(method, url, **kwargs):
        return StubResp(400, {"error": "validation failed"})

    monkeypatch.setattr("requests.request", always_400)
    monkeypatch.setattr("requests.post", lambda url, **kwargs: StubResp(200, {"access_token": "X", "expires_in": 3600}))

    with pytest.raises(m.EtsyError) as exc_info:
        m.etsy_create_draft({"title": "Dino"}, str(pdf), None, price=4.99)
    assert exc_info.value.status_code == 400


# ---------- lifecycle: draft_failed, never published ----------
def _story_file(books: Path):
    books.mkdir(parents=True, exist_ok=True)
    (books / "story.json").write_text(json.dumps({
        "etsy": {"title": "t", "description": "d", "tags": ["a"]},
        "title": "t",
        "character_sheet": "x", "style": "x",
        "pages": [{"text": "x", "image_prompt": "x"}] * 12,
    }), encoding="utf-8")


def test_publish_gate_no_keys_fails(tmp_env, tmp_path):
    _clear_cfg()
    from agents.departments.books.publishing import run

    # make a fake story + pdf on disk so the gate passes file checks
    books = cfg.BOOKS_DIR / "test_book_1"
    _story_file(books)
    (books / "book.pdf").write_bytes(b"%PDF-1.7 placeholder")
    svc.upsert_product("test_book_1", "Test Book", status="pdf",
                       pdf_path=str(books / "book.pdf"))
    out = run("test_book_1 publish", slug="test_book_1", human_confirmed=True)
    assert out["ok"] is False
    assert "not configured" in (out.get("error") or "").lower()
    product = svc.get_product("test_book_1")
    assert product["status"] == "draft_failed"
    assert product["status"] != "published"


def test_publish_success_real_id_gets_draft_created(tmp_env, tmp_path, monkeypatch):
    _make_cfg()
    from agents.departments.books.publishing import run

    books = cfg.BOOKS_DIR / "test_book_1"
    _story_file(books)
    (books / "book.pdf").write_bytes(b"%PDF-1.7 hi")
    svc.upsert_product("test_book_1", "Test Book", status="pdf",
                       pdf_path=str(books / "book.pdf"))

    def fake_request(method, url, **kwargs):
        if "listings" in url and method == "POST" and "files" not in url and "images" not in url:
            return StubResp(200, {"listing_id": "real-123"})
        return StubResp(200, {})

    monkeypatch.setattr("requests.request", fake_request)
    monkeypatch.setattr("requests.post", lambda url, **kwargs: StubResp(200, {"access_token": "Y", "expires_in": 3600}))

    out = run("test_book_1 publish", slug="test_book_1", human_confirmed=True)
    assert out["ok"] is True
    product = svc.get_product("test_book_1")
    assert product["status"] == "draft_created"
    assert product["status"] != "published"


def test_publish_failure_never_marks_published(tmp_env, tmp_path, monkeypatch):
    _make_cfg()
    from agents.departments.books.publishing import run

    books = cfg.BOOKS_DIR / "test_book_1"
    _story_file(books)
    (books / "book.pdf").write_bytes(b"%PDF-1.7 hi")
    svc.upsert_product("test_book_1", "Test Book", status="pdf",
                       pdf_path=str(books / "book.pdf"))

    def always_fail(method, url, **kwargs):
        return StubResp(503, "service unavailable")

    monkeypatch.setattr("requests.request", always_fail)
    monkeypatch.setattr("requests.post", lambda url, **kwargs: StubResp(200, {"access_token": "Z", "expires_in": 3600}))

    out = run("test_book_1 publish", slug="test_book_1", human_confirmed=True)
    assert out["ok"] is False
    product = svc.get_product("test_book_1")
    assert product["status"] == "draft_failed"
    assert product["status"] != "published"
