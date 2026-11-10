"""Phase 4 — Opportunity engine: engine runs with fake LLM and writes deduped opportunities.

This proves the crank turns end-to-end. No real scores predicted — just the current weights.
"""
import json
import os

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
    dbmod.reset_store_for_tests()
    yield tmp_path
    dbmod.reset_store_for_tests()


def test_opportunity_engine_runs_and_dedupes(tmp_env, monkeypatch):
    monkeypatch.setenv("AIHQ_FAKE_LLM", "1")
    monkeypatch.setenv("AIHQ_ALLOW_DEMO", "1")
    from agents.workflows.opportunity_engine import run as run_engine

    out = run_engine("back to school niches", task_id=None)
    assert out["ok"], out.get("error")
    rows1 = svc.list_opportunities(status="new")
    assert len(rows1) >= 1
    n = len(rows1)

    # run again — should NOT double the count (dedupe by key)
    out2 = run_engine("back to school niches", task_id=None)
    assert out2["ok"], out2.get("error")
    rows2 = svc.list_opportunities(status="new")
    assert len(rows2) == n
