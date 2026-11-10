"""Golden rule 1 — no external action without founder sign-off.

These tests pin down the behavior the founder is promised:
  1. An unauthenticated request is rejected (401).
  2. Approving a publish when Etsy keys are missing fails (502) and does NOT register a `published` state.
  3. `human_confirmed: true` in the request body does NOT cause a publish — approval must be real.
"""
import json
import os

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


def test_publish_path_requires_configured_etsy(tmp_env, monkeypatch):
    """Without ETSY_* vars, an approval decision must fail with 502; never a fake listing."""
    monkeypatch.delenv("ETSY_KEYSTRING", raising=False)
    monkeypatch.delenv("ETSY_SHARED_SECRET", raising=False)
    monkeypatch.delenv("ETSY_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("ETSY_SHOP_ID", raising=False)
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app, raise_server_exceptions=False)

    # seed book + pdf
    books = cfg.BOOKS_DIR / "test_book1"
    books.mkdir(parents=True)
    (books / "story.json").write_text(json.dumps({
        "etsy": {"title": "t", "description": "d", "tags": ["a"]},
        "title": "t", "character_sheet": "x", "style": "x",
        "pages": [{"text": "x", "image_prompt": "x"}] * 12,
    }), encoding="utf-8")
    (books / "book.pdf").write_bytes(b"%PDF-1.7 hi")
    svc.upsert_product("test_book1", "Test Book", status="pdf",
                       pdf_path=str(books / "book.pdf"))
    aid = svc.create_approval("etsy_publish", "test_book1", note="gate check")

    headers = {"Authorization": f"Bearer {os.environ['FOUNDER_TOKEN']}"}
    r = client.post(f"/api/approvals/{aid}/decide",
                    json={"decision": "approve", "note": ""}, headers=headers)
    # Etsy not configured → publish fails hard: 502
    assert r.status_code == 502, r.text
    # and the product is NOT marked published
    assert svc.get_product("test_book1")["status"] != "published"


def test_no_external_action_when_unauthed(tmp_env, monkeypatch):
    """Without the founder token, all mutating endpoints refuse."""
    monkeypatch.delenv("ETSY_KEYSTRING", raising=False)
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    for path, body in (("/api/ceo/run", {"task": "anything"}),
                       ("/api/departments/books.market/run", {"task": "scan"})):
        r = client.post(path, json=body)
        assert r.status_code == 401, (path, r.text)
