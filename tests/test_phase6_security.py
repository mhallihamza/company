"""Phase 6 — security & reliability hard gates.

Health contract, token compare, CEO word-boundary matching.
"""
import os


def test_health_returns_only_status_ok():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_admin_health_requires_token(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    monkeypatch.setenv("FOUNDER_TOKEN", "test-founder-token-000000000000")
    client = TestClient(app)
    r = client.get("/api/admin/health")
    assert r.status_code == 401
    r = client.get("/api/admin/health",
                   headers={"Authorization": "Bearer test-founder-token-000000000000"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_ceo_keyword_routing_uses_word_boundaries():
    # "Qatar" is not "qa"; neither substring nor QA should be selected
    from agents.ceo.graph import route_task
    assert route_task("Qatar back to school niches") != "qa"
    assert route_task("run the QA checker") == "qa"
    assert route_task("مسافة إلى مطار الشام") != "qa"
