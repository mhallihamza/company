"""وحدة قاعدة البيانات — Postgres (Supabase) أو سقوط تلقائي إلى SQLite.

الجداول (بالضبط حسب البنية المطلوبة):
  departments, agents, tasks, task_executions, opportunities, products,
  reports, approvals, audit_logs, budgets, settings — كلها تحمل workspace_id.
أي جدول يحمل workspace_id='default' الآن، ليستعد التعدد لاحقاً.
"""
from __future__ import annotations
import contextlib
import json
import os
import re
import sqlite3
import threading
from typing import Any, Iterator

from backend.app import config

_PG_DDL = [
    """CREATE TABLE IF NOT EXISTS departments (
        dept_id     BIGSERIAL PRIMARY KEY,
        key         TEXT UNIQUE NOT NULL,
        title_ar    TEXT,
        title_en    TEXT,
        policy      TEXT DEFAULT 'none',
        workspace_id TEXT DEFAULT 'default',
        updated_at  TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS agents (
        agent_id    BIGSERIAL PRIMARY KEY,
        dept_key    TEXT NOT NULL,
        name        TEXT NOT NULL,
        model       TEXT,
        version     TEXT DEFAULT '1.0.0',
        workspace_id TEXT DEFAULT 'default')""",
    """CREATE TABLE IF NOT EXISTS tasks (
        task_id     BIGSERIAL PRIMARY KEY,
        type        TEXT NOT NULL,
        domain      TEXT NOT NULL,
        ref         TEXT,
        input_text  TEXT,
        detail      TEXT,
        status      TEXT DEFAULT 'running',
        created_at  TIMESTAMPTZ DEFAULT now(),
        finished_at TIMESTAMPTZ,
        workspace_id TEXT DEFAULT 'default')""",
    """CREATE TABLE IF NOT EXISTS task_executions (
        exec_id     BIGSERIAL PRIMARY KEY,
        task_id     BIGINT NOT NULL REFERENCES tasks(task_id),
        agent       TEXT,
        started_at  TIMESTAMPTZ DEFAULT now(),
        finished_at TIMESTAMPTZ,
        status      TEXT DEFAULT 'running',
        tokens_used INTEGER DEFAULT 0,
        detail      TEXT,
        workspace_id TEXT DEFAULT 'default')""",
    """CREATE TABLE IF NOT EXISTS market_profiles (
        profile_id   BIGSERIAL PRIMARY KEY,
        country      TEXT NOT NULL,
        language     TEXT NOT NULL,
        currency     TEXT NOT NULL,
        dir          TEXT DEFAULT 'ltr',
        font         TEXT,
        seeds        TEXT,                           -- JSON list of seed keywords
        seasonal     TEXT,                           -- JSON seasonal calendar
        enabled      BOOLEAN DEFAULT TRUE,
        created_at   TIMESTAMPTZ DEFAULT now(),
        UNIQUE(country, language))""",
    """CREATE TABLE IF NOT EXISTS opportunities (
        opportunity_id BIGSERIAL PRIMARY KEY,
        sector      TEXT NOT NULL,
        title       TEXT NOT NULL,
        niche       TEXT,
        score       DOUBLE PRECISION,
        status      TEXT DEFAULT 'new',
        source      TEXT DEFAULT 'demo',
        evidence    TEXT,
        payload     TEXT,
        workspace_id TEXT DEFAULT 'default',
        created_at  TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS products (
        product_id  BIGSERIAL PRIMARY KEY,
        slug        TEXT UNIQUE NOT NULL,
        title       TEXT NOT NULL,
        status      TEXT DEFAULT 'story',
        pdf_path    TEXT,
        cover_path  TEXT,
        final_file  TEXT,
        price_usd   REAL DEFAULT 4.99,
        publish_targets TEXT DEFAULT '[\"etsy\",\"kdp_paperback\",\"kdp_ebook\"]',
        workspace_id TEXT DEFAULT 'default',
        created_at  TIMESTAMPTZ DEFAULT now(),
        updated_at  TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS reports (
        report_id   BIGSERIAL PRIMARY KEY,
        kind        TEXT DEFAULT 'md',
        path        TEXT,
        title       TEXT,
        source      TEXT DEFAULT 'demo',
        evidence    TEXT,
        content     TEXT,
        workspace_id TEXT DEFAULT 'default',
        created_at  TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS approvals (
        approval_id BIGSERIAL PRIMARY KEY,
        kind        TEXT NOT NULL,
        ref         TEXT NOT NULL,
        status      TEXT DEFAULT 'pending',
        note        TEXT,
        decided_at  TIMESTAMPTZ,
        workspace_id TEXT DEFAULT 'default',
        created_at  TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS audit_logs (
        log_id      BIGSERIAL PRIMARY KEY,
        task_id     BIGINT,
        actor       TEXT NOT NULL,
        action      TEXT NOT NULL,
        detail      TEXT,
        workspace_id TEXT DEFAULT 'default',
        created_at  TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS product_tests (
        test_id      BIGSERIAL PRIMARY KEY,
        opportunity_id BIGINT NOT NULL REFERENCES opportunities(opportunity_id),
        channel       TEXT NOT NULL,
        views         INTEGER DEFAULT 0,
        favorites     INTEGER DEFAULT 0,
        sales         INTEGER DEFAULT 0,
        test_start    TIMESTAMPTZ,
        test_end      TIMESTAMPTZ,
        notes         TEXT,
        workspace_id  TEXT DEFAULT 'default',
        created_at    TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS budgets (
        budget_id   BIGSERIAL PRIMARY KEY,
        workspace_id TEXT UNIQUE DEFAULT 'default',
        monthly_limit_usd DOUBLE PRECISION DEFAULT 50.0,
        used_usd    DOUBLE PRECISION DEFAULT 0.0)""",
    """CREATE TABLE IF NOT EXISTS settings (
        key         TEXT PRIMARY KEY,
        value       TEXT,
        updated_at  TIMESTAMPTZ DEFAULT now())""",
]

_SQLITE_DDL = [s.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
               .replace("TIMESTAMPTZ DEFAULT now()", "TEXT DEFAULT CURRENT_TIMESTAMP")
               .replace("TIMESTAMPTZ", "TEXT")
               .replace("DOUBLE PRECISION", "REAL") for s in _PG_DDL]

_lock = threading.RLock()
_store: "Store | None" = None


class Store:
    def __init__(self) -> None:
        self.kind, self.backend_label, self.pg_diag = self._connect()
        self._ensure_schema()

    import re
_DSN_RE = re.compile(r"(postgres(?:ql)?|postgresql\+psycopg2)(\+[a-z0-9]+)?:\/\/[^\s]+", re.I)
_SECRET_PARTS = re.compile(
    r"(host|port|user(?:name)?|password|passwd|database|dbname)\s*[:=]\s*[\w.@%{}_\-]+",
    re.I,
)
# Supabase names this refname in several forms
_SUPA_REF = re.compile(r"postgres\.[a-z0-9]{20,}|[a-z0-9]{20,}\.supabase\.co?m?|pooler\.supabase\.com", re.I)


def _sanitize(msg: str) -> str:
    """Strip host, user, password, DSN details from any connection error text."""
    out = _DSN_RE.sub("[redacted dsn]", str(msg))
    out = _SECRET_PARTS.sub(r"\1=[redacted]", out)
    out = _SUPA_REF.sub("[redacted]", out)
    return out[:500]


def _pg_diag_text(err: Exception | None, timed_out: bool) -> str:
    if timed_out:
        return "psycopg: connection timed out"
    if err is None:
        return ""
    return f"psycopg: {_sanitize(err)}"


class Store:
    def __init__(self) -> None:
        self._pool = None          # psycopg_pool.ConnectionPool for PG, None for SQLite
        self.kind, self.backend_label, self.pg_diag = self._connect()
        self._ensure_schema()

    # ---------- اتصال ----------
    def _connect(self):
        backend = config.DB_BACKEND
        if backend in ("auto", "supabase") and config.DATABASE_URL:
            import threading as _th

            result: dict = {}
            timed_out = _th.Event()

            def _attempt():
                try:
                    from psycopg_pool import ConnectionPool
                    min_size = int(os.getenv("DB_POOL_MIN", "1"))
                    max_size = int(os.getenv("DB_POOL_MAX", "5"))
                    max_idle = int(os.getenv("DB_POOL_MAX_IDLE", "60"))
                    max_lifetime = int(os.getenv("DB_POOL_MAX_LIFETIME", "300"))
                    pool = ConnectionPool(
                        config.DATABASE_URL,
                        min_size=min_size,
                        max_size=max_size,
                        max_idle=max_idle,
                        max_lifetime=max_lifetime,
                        check=ConnectionPool.check_connection,
                        kwargs={"autocommit": True, "connect_timeout": 6},
                        open=True,
                    )
                    result["pool"] = pool
                except Exception as e:  # noqa: BLE001
                    result["err"] = e

            thread = _th.Thread(target=_attempt, daemon=True)
            thread.start()
            thread.join(10)

            pool = result.get("pool")
            if pool is not None:
                try:
                    with pool.connection(timeout=6) as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1")
                    self._pool = pool
                    return "pg", "Supabase Postgres", ""
                except Exception as e:  # noqa: BLE001
                    try:
                        pool.close()
                    except Exception:  # noqa: BLE001
                        pass
                    result["err"] = e

            diag = _pg_diag_text(result.get("err") if result.get("err") else None,
                                 timed_out=timed_out.is_set())
            if backend == "supabase":
                raise RuntimeError(f"Supabase connection failed: {diag}")
            config.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            return "sqlite", f"SQLite ({config.SQLITE_PATH.name})", diag

        config.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        return "sqlite", f"SQLite ({config.SQLITE_PATH.name})", ""

    def _close_pool(self) -> None:
        pool = getattr(self, "_pool", None)
        if pool is not None:
            try:
                pool.close()
            except Exception:  # noqa: BLE001
                pass
            self._pool = None

    def _ensure_schema(self) -> None:
        with _lock:
            ddl = _PG_DDL if self.kind == "pg" else _SQLITE_DDL
            try:
                if self.kind == "pg":
                    with self._pool.connection() as conn:  # type: ignore[union-attr]
                        conn.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS publish_targets TEXT")
                        conn.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS price_usd REAL DEFAULT 4.99")
                        conn.execute("ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'demo'")
                        conn.execute("ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS evidence TEXT")
                        conn.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'demo'")
                        conn.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS evidence TEXT")
                else:
                    conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
                    try:
                        have_p = {r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()}
                        if "publish_targets" not in have_p:
                            conn.execute("ALTER TABLE products ADD COLUMN publish_targets TEXT DEFAULT '[\"etsy\",\"kdp_paperback\",\"kdp_ebook\"]'")
                        if "price_usd" not in have_p:
                            conn.execute("ALTER TABLE products ADD COLUMN price_usd REAL DEFAULT 4.99")
                        have_o = {r[1] for r in conn.execute("PRAGMA table_info(opportunities)").fetchall()}
                        if "source" not in have_o:
                            conn.execute("ALTER TABLE opportunities ADD COLUMN source TEXT DEFAULT 'demo'")
                        if "evidence" not in have_o:
                            conn.execute("ALTER TABLE opportunities ADD COLUMN evidence TEXT")
                        have_r = {r[1] for r in conn.execute("PRAGMA table_info(reports)").fetchall()}
                        if "source" not in have_r:
                            conn.execute("ALTER TABLE reports ADD COLUMN source TEXT DEFAULT 'demo'")
                        if "evidence" not in have_r:
                            conn.execute("ALTER TABLE reports ADD COLUMN evidence TEXT")
                        conn.commit()
                    finally:
                        conn.close()
            except Exception:  # noqa: BLE001 — safe migration: tables may be fresh
                pass
            if self.kind == "pg":
                with self._pool.connection() as conn:  # type: ignore[union-attr]
                    for stmt in ddl:
                        conn.execute(stmt)
            else:
                conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
                try:
                    for stmt in ddl:
                        conn.execute(stmt)
                    conn.commit()
                finally:
                    conn.close()
            if self._scalar("SELECT count(*) FROM budgets") == 0:
                self._execute(
                    "INSERT INTO budgets (workspace_id, monthly_limit_usd) VALUES ('default', 50.0)")
            if self._scalar("SELECT count(*) FROM settings WHERE key='autonomy_level'") == 0:
                self._execute(
                    "INSERT INTO settings (key, value) VALUES ('autonomy_level', '1')")

    # ---------- أدوات داخلية ----------
    @contextlib.contextmanager
    def _cur(self) -> Iterator[Any]:
        if self.kind == "pg":
            from psycopg.rows import dict_row
            assert self._pool is not None
            with self._pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    yield cur
        else:
            conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()

    def _execute(self, sql: str, params: tuple = ()) -> None:
        ph = "%s" if self.kind == "pg" else "?"
        sql = sql.replace("?", ph) if self.kind == "pg" else sql
        with self._cur() as cur:
            cur.execute(sql, params)

    def _scalar(self, sql: str, params: tuple = ()) -> int:
        with self._cur() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        if row is None:
            return 0
        if isinstance(row, dict):
            return int(next(iter(row.values()), 0) or 0)
        return int(row[0] or 0)

    # ========= مهام التحرير المباشرة (audit/tasks/executions) =========
    def create_task(self, task_type: str, domain: str, ref: str | None,
                    input_text: str = "") -> int:
        sql = ("INSERT INTO tasks (type, domain, ref, input_text) "
               "VALUES (?,?,?,?) RETURNING task_id")
        with self._cur() as cur:
            cur.execute(sql.replace("?", "%s" if self.kind == "pg" else "?") if self.kind == "pg" else sql,
                        (task_type, domain, ref, input_text[:2000]))
            row = cur.fetchone()
            return int(row["task_id"] if isinstance(row, dict) else row[0])

    def finish_task(self, task_id: int, status: str, detail: str = "") -> None:
        self._execute("UPDATE tasks SET status=?, finished_at=CURRENT_TIMESTAMP, detail=? WHERE task_id=?",
                      (status, detail[:2000], task_id))

    def create_execution(self, task_id: int, agent: str) -> int:
        sql = ("INSERT INTO task_executions (task_id, agent) "
               "VALUES (?,?) RETURNING exec_id")
        with self._cur() as cur:
            cur.execute(sql.replace("?", "%s" if self.kind == "pg" else "?") if self.kind == "pg" else sql,
                        (task_id, agent))
            row = cur.fetchone()
            return int(row["exec_id"] if isinstance(row, dict) else row[0])

    def finish_execution(self, exec_id: int, status: str, detail: str = "", tokens: int = 0) -> None:
        self._execute("UPDATE task_executions SET status=?, finished_at=CURRENT_TIMESTAMP, detail=?, tokens_used=? WHERE exec_id=?",
                      (status, detail[:2000], tokens, exec_id))

    def audit(self, task_id: int | None, actor: str, action: str, detail: str = "") -> None:
        self._execute("INSERT INTO audit_logs (task_id, actor, action, detail) VALUES (?,?,?,?)",
                      (task_id, actor, action, detail[:2000]))

    def _row_dict(self, row: Any) -> dict:
        if row is None:
            return {}
        if isinstance(row, dict):
            return dict(row)
        keys = [d[0] for d in row.description] if hasattr(row, "description") else []
        return dict(zip(keys, row)) if keys else dict(row)

    def _rows(self, sql: str, params: tuple = ()) -> list[dict]:
        sql = sql.replace("?", "%s") if self.kind == "pg" else sql
        with self._cur() as cur:
            cur.execute(sql, params)
            return [self._row_dict(r) for r in cur.fetchall()]

    # ========= الاستعلام العام =========
    def q(self, sql: str, params: tuple = ()) -> list[dict]:
        return self._rows(sql, params)


def get_store() -> Store:
    global _store
    with _lock:
        if _store is None:
            _store = Store()
        return _store


def reset_store_for_tests() -> None:
    global _store
    with _lock:
        if _store is not None:
            _store._close_pool()
        _store = None


# تغطيات خدمة عالية المستوى
def audit(task_id: int | None, actor: str, action: str, detail: str = "") -> None:
    try:
        get_store().audit(task_id, actor, action, detail)
    except Exception:  # noqa: BLE001 — التدقيق لا يكسر المسار الرئيسي
        pass
