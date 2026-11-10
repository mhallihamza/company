"""Item 5 — db pool: SQL types this store handles."""
import threading
import time

import pytest

import backend.app.config as cfg
from backend.app.db import _sanitize


def test_sanitize_redacts_host_password_user_and_dsn():
    where_it_used_to_leak = (
        "psycopg.OperationalError: connection to server at \"aws-0-eu-west-1.pooler.supabase.com\" "
        "(User=postgres.nbnuvutoildmhectqchr), port 6543 failed: password authentication failed"
        " — full DSN: postgresql://postgres:HAmza1995dacia@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
    )
    out = _sanitize(where_it_used_to_leak)
    assert "HAmza1995dacia" not in out
    assert "nbnuvutoildmhectqchr" not in out
    assert "pooler.supabase.com" not in out
    assert "postgresql://" not in out
    # must still carry useful status info
    assert "[redacted" in out.lower()


def test_sqlite_fallback_thread_safe(tmp_path, monkeypatch):
    """All CRUD ops from 10 threads land in the same sqlite file without race."""
    monkeypatch.setattr(cfg, "BOOKS_DIR", tmp_path / "books")
    monkeypatch.setattr(cfg, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cfg, "SQLITE_PATH", tmp_path / "data" / "test.db")
    monkeypatch.setattr(cfg, "DB_BACKEND", "sqlite")
    # keep using sqlite path deterministically, not cfg.DATABASE_URL
    monkeypatch.setattr(cfg, "DATABASE_URL", "")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import backend.app.db as dbmod
    dbmod.reset_store_for_tests()
    store = dbmod.Store()
    errors = []

    def _work(i):
        try:
            store.create_task("test", "qa", ref=f"slot_{i}")
            n = store._scalar("SELECT count(*) FROM tasks")
            store.audit(None, "test", "check", f"count={n}")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_work, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert store._scalar("SELECT count(*) FROM tasks") == 10


@pytest.mark.skipif(not __import__("os").getenv("DATABASE_URL"),
                    reason="DATABASE_URL not set — Postgres pool test skipped")
def test_pg_pool_recovers_after_forced_close(tmp_path, monkeypatch):
    """PG pool checkout: close a pooled connection mid-flight, next call must succeed."""
    monkeypatch.setattr(cfg, "BOOKS_DIR", tmp_path / "books")
    monkeypatch.setattr(cfg, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cfg, "SQLITE_PATH", tmp_path / "data" / "test.db")
    monkeypatch.setattr(cfg, "DB_BACKEND", "supabase")
    import backend.app.db as dbmod
    dbmod.reset_store_for_tests()
    store = dbmod.Store()
    before = store._scalar("SELECT 1")
    # forcefully kill a pooled connection
    try:
        with store._pool.connection() as conn:  # type: ignore[union-attr]
            with conn.cursor() as cur:
                cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = pg_backend_pid()")
    except Exception:  # noqa: BLE001 — termination may raise; that's the point
        pass
    after = store._scalar("SELECT 1")
    assert after == 1
