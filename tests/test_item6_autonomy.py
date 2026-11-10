"""Item 6 — autonomy_level policy + token plumbing + observability split.

The gate lives in two places:
  * POST /api/departments/{key}/run → 403 before any execution
  * CEO graph _execute        → blocked execution recorded with status='blocked'
Publishing (human_required) is independent of autonomy level — approvals table still rules.
"""
import json

import pytest

import backend.app.config as cfg
import backend.app.db as dbmod
from backend.app.services import store as svc


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


# ---------- unit gate ----------

@pytest.mark.parametrize("level,key,expected", [
    (0, "intelligence", False),
    (0, "books.content", False),
    (0, "books.publishing", False),
    (1, "intelligence", True),
    (1, "affiliate", True),
    (1, "finance", True),
    (1, "qa", True),
    (1, "books.market", True),
    (1, "books.content", False),
    (1, "marketing", False),
    (1, "books.publishing", False),
    (2, "books.content", True),
    (2, "marketing", True),
    (2, "books.publishing", True),   # allowed by autonomy — but human_required still demands approval
    (2, "product", True),
    (2, "design", True),
    (3, "books.content", True),
])
def test_department_allowed(level, key, expected):
    from backend.app.services.autonomy import department_allowed
    assert department_allowed(level, key) is expected


def test_allowed_departments_lists_expected():
    from backend.app.services.autonomy import allowed_departments
    assert allowed_departments(0) == []
    assert "intelligence" in allowed_departments(1)
    assert "books.content" in allowed_departments(2)


# ---------- API gate ----------

def test_api_run_blocked_at_autonomy_zero(tmp_env, monkeypatch):
    monkeypatch.setenv("FOUNDER_TOKEN", "test-founder-token")
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    s = svc.set_setting("autonomy_level", "0")
    headers = {"Authorization": "Bearer test-founder-token"}
    r = client.post("/api/departments/intelligence/run",
                    json={"task": "scan opportunities"}, headers=headers)
    assert r.status_code == 403
    assert "autonomy" in r.json().get("detail", "").lower()
    # even the CEO cannot run at 0
    r2 = client.post("/api/ceo/run",
                     json={"task": "run the floor"}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["ok"] is False or "blocked" in str(r2.json()).lower()


def test_api_run_level_one_blocks_content(tmp_env, monkeypatch):
    monkeypatch.setenv("FOUNDER_TOKEN", "test-founder-token")
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    svc.set_setting("autonomy_level", "1")
    headers = {"Authorization": "Bearer test-founder-token"}
    r_content = client.post("/api/departments/books.content/run",
                            json={"task": "write book"}, headers=headers)
    assert r_content.status_code == 403
    r_intel = client.post("/api/departments/intelligence/run",
                          json={"task": "scan opportunities"}, headers=headers)
    assert r_intel.status_code == 200


# ---------- token plumbing: unmeasured for fake LLM, NULL in the DB ----------

def test_usage_snapshot_unmeasured_for_fake_llm(tmp_env, monkeypatch):
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    from agents import llm as _llm

    _llm.reset_usage_counter()
    model = _llm.get_chat_model()
    model.invoke("[ROLE:orchestrator]\nanything")
    snap = _llm.usage_snapshot()
    assert snap is not None
    assert snap["calls"] >= 1
    assert snap["measured_calls"] == 0
    assert snap["total_tokens"] is None
    assert snap["source"] == "unmeasured"


def test_fake_llm_execution_records_null_tokens(tmp_env, monkeypatch):
    monkeypatch.setenv("FOUNDER_TOKEN", "test-founder-token")
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    svc.set_setting("autonomy_level", "1")
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    headers = {"Authorization": "Bearer test-founder-token"}
    client.post("/api/departments/qa/run",
                json={"task": "QA check"}, headers=headers)
    rows = svc.list_executions(limit=5)
    assert rows, "expected executions to be recorded"
    toks = [r.get("tokens_used") for r in rows]
    # every unmeasured call must be NULL — never an invented 0
    assert all(t is None for t in toks)


# ---------- observability keys ----------

def test_observability_exposes_measured_vs_unmeasured(tmp_env, monkeypatch):
    monkeypatch.setenv("FOUNDER_TOKEN", "test-founder-token")
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    headers = {"Authorization": "Bearer test-founder-token"}
    client.post("/api/departments/qa/run",
                json={"task": "QA check"}, headers=headers)
    r = client.get("/api/observability", headers=headers)
    assert r.status_code == 200
    body = r.json()
    for key in ("tokens_measured_total", "executions_with_token_data",
                "executions_unmeasured", "tokens_source", "budget_estimate_usd"):
        assert key in body, f"missing {key} in observability payload"
    assert body["executions_with_token_data"] >= 0
    assert body["tokens_source"] in {"measured", "unmeasured", "measured+unmeasured"}
