"""طبقة التخزين — Supabase Postgres أساسياً، مع تراجع تلقائي إلى SQLite محلي.

كل الدوال آمنة الاستدعاء دون تهيئة صريحة: تُهيّأ المخططات (DDL) مرة واحدة
عند أول استخدام. عند فشل الاتصال بـ Supabase يُسجَّل تحذير ويُستخدم SQLite.
"""
from __future__ import annotations
import os
import sqlite3
import threading
import datetime as _dt
from pathlib import Path
from kidbook import config

_lock = threading.RLock()   # RLock: _ensure_schema يُستدعى تحت get_store بنفس القفل
_store = None

_DDL_PG = """
CREATE TABLE IF NOT EXISTS kidbook_books (
    id              BIGSERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    title           TEXT,
    idea            TEXT,
    language        TEXT DEFAULT 'ar',
    status          TEXT DEFAULT 'story_draft',
    pdf_path        TEXT,
    cover_path      TEXT,
    page_count      INTEGER,
    etsy_listing_id TEXT,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS kidbook_runs (
    id          BIGSERIAL PRIMARY KEY,
    run_type    TEXT NOT NULL,
    domain      TEXT,
    ref         TEXT,
    status      TEXT DEFAULT 'running',
    detail      TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS kidbook_run_logs (
    id          BIGSERIAL PRIMARY KEY,
    run_id      BIGINT REFERENCES kidbook_runs(id) ON DELETE CASCADE,
    level       TEXT DEFAULT 'info',
    message     TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS kidbook_reports (
    id          BIGSERIAL PRIMARY KEY,
    path        TEXT,
    content     TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS kidbook_opportunities (
    id          BIGSERIAL PRIMARY KEY,
    sector      TEXT NOT NULL,            -- affiliate | intelligence | books
    title       TEXT NOT NULL,
    niche       TEXT,
    score       DOUBLE PRECISION,
    status      TEXT DEFAULT 'new',       -- new | watching | pursuing | archived
    payload     TEXT,                      -- JSON كامل
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS kidbook_approvals (
    id          BIGSERIAL PRIMARY KEY,
    kind        TEXT NOT NULL,            -- etsy_publish
    ref         TEXT NOT NULL,            -- slug أو المنتج
    status      TEXT DEFAULT 'pending',   -- pending | approved | rejected
    note        TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    decided_at  TIMESTAMPTZ
);
"""

_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS kidbook_books (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT UNIQUE NOT NULL,
    title           TEXT,
    idea            TEXT,
    language        TEXT DEFAULT 'ar',
    status          TEXT DEFAULT 'story_draft',
    pdf_path        TEXT,
    cover_path      TEXT,
    page_count      INTEGER,
    etsy_listing_id TEXT,
    error           TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS kidbook_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type    TEXT NOT NULL,
    domain      TEXT,
    ref         TEXT,
    status      TEXT DEFAULT 'running',
    detail      TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS kidbook_run_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER REFERENCES kidbook_runs(id) ON DELETE CASCADE,
    level       TEXT DEFAULT 'info',
    message     TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS kidbook_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT,
    content     TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS kidbook_opportunities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sector      TEXT NOT NULL,
    title       TEXT NOT NULL,
    niche       TEXT,
    score       REAL,
    status      TEXT DEFAULT 'new',
    payload     TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS kidbook_approvals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    ref         TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',
    note        TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    decided_at  TEXT
);
"""


class Store:
    """واجهة موحّدة فوق Postgres (psycopg) أو SQLite."""

    def __init__(self):
        self.kind, self.backend_label = self._connect()
        self._ensure_schema()

    # ---------- اتصال ----------
    def _connect(self):
        cfg = config.DB_BACKEND
        if cfg in ("auto", "supabase") and config.DATABASE_URL:
            import threading
            result: dict = {}

            def _attempt():
                try:
                    import psycopg
                    result["conn"] = psycopg.connect(
                        config.DATABASE_URL, connect_timeout=6, autocommit=True)
                except Exception as e:  # noqa: BLE001
                    result["err"] = e

            # libpq قد يتجاهل connect_timeout أثناء حل DNS على Windows،
            # لذلك نحصر المحاولة كلها في خيط مع مهلة صلبة.
            thread = threading.Thread(target=_attempt, daemon=True)
            thread.start()
            thread.join(12)
            if "conn" in result:
                self._conn = result["conn"]
                return "pg", "Supabase Postgres"
            reason = (f"psycopg: {result['err']}" if "err" in result
                      else "psycopg: انتهت مهلة الاتصال (12 ثانية) — غالباً شبكة/DNS")
            if cfg == "supabase":
                raise RuntimeError(f"فشل الاتصال بـ Supabase: {reason}") from \
                    result.get("err", RuntimeError(reason))
            self._pg_error = reason
        config.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        return "sqlite", f"SQLite ({config.SQLITE_PATH.name})"

    def _ensure_schema(self):
        with _lock:
            if self.kind == "pg":
                for stmt in _DDL_PG.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        self._conn.execute(stmt)
            else:
                self._conn.executescript(_DDL_SQLITE)

    def _cur(self):
        """مدير سياق موحد: pg أو sqlite (Python 3.13 أزال CM من مؤشر sqlite)."""
        import contextlib

        @contextlib.contextmanager
        def cm():
            if self.kind == "pg":
                from psycopg.rows import dict_row
                with self._conn.cursor(row_factory=dict_row) as cur:
                    yield cur
            else:
                cur = self._conn.cursor()
                try:
                    yield cur
                    self._conn.commit()
                except Exception:
                    self._conn.rollback()
                    raise
                finally:
                    cur.close()
        return cm()

    def ping(self):
        try:
            with self._cur() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True, self.backend_label
        except Exception as e:  # noqa: BLE001
            return False, f"{self.backend_label} — تعذر الاتصال: {e}"

    # ---------- الكتب ----------
    def create_book(self, slug, title, idea, language, status="story_draft"):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(
                f"INSERT INTO kidbook_books (slug, title, idea, language, status) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph}) "
                f"ON CONFLICT (slug) DO UPDATE SET title=excluded.title, idea=excluded.idea, "
                f"language=excluded.language, error=NULL, updated_at=CURRENT_TIMESTAMP "
                f"RETURNING id",
                (slug, title, idea, language, status))
            return cur.fetchone()["id"] if self.kind == "pg" else cur.fetchone()[0]

    def update_book(self, slug, **fields):
        if not fields:
            return
        ph = "%s" if self.kind == "pg" else "?"
        cols = ", ".join(f"{k}={ph}" for k in fields)
        vals = list(fields.values()) + [slug]
        with self._cur() as cur:
            cur.execute(
                f"UPDATE kidbook_books SET {cols}, updated_at=CURRENT_TIMESTAMP WHERE slug={ph}",
                vals)

    def get_book(self, slug):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(f"SELECT * FROM kidbook_books WHERE slug={ph}", (slug,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_books(self, limit=200):
        with self._cur() as cur:
            cur.execute(f"SELECT * FROM kidbook_books ORDER BY id DESC LIMIT {int(limit)}")
            return [dict(r) for r in cur.fetchall()]

    # ---------- التشغيلات والسجلات ----------
    def create_run(self, run_type, domain=None, ref=None):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(
                f"INSERT INTO kidbook_runs (run_type, domain, ref) VALUES ({ph},{ph},{ph}) RETURNING id",
                (run_type, domain, ref))
            row = cur.fetchone()
            return row["id"] if self.kind == "pg" else row[0]

    def finish_run(self, run_id, status, detail=None):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(
                f"UPDATE kidbook_runs SET status={ph}, detail={ph},"
                f" finished_at=CURRENT_TIMESTAMP WHERE id={ph}",
                (status, (detail or "")[:2000], run_id))

    def log(self, run_id, message, level="info"):
        ph = "%s" if self.kind == "pg" else "?"
        try:
            with self._cur() as cur:
                cur.execute(
                    f"INSERT INTO kidbook_run_logs (run_id, level, message) VALUES ({ph},{ph},{ph})",
                    (run_id, level, str(message)[:4000]))
        except Exception:
            pass  # السجل لا يجب أن يُفشل العملية

    def list_runs(self, limit=50):
        with self._cur() as cur:
            cur.execute(f"SELECT * FROM kidbook_runs ORDER BY id DESC LIMIT {int(limit)}")
            return [dict(r) for r in cur.fetchall()]

    def list_logs(self, run_id, limit=500):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(
                f"SELECT * FROM kidbook_run_logs WHERE run_id={ph} ORDER BY id ASC LIMIT {int(limit)}",
                (run_id,))
            return [dict(r) for r in cur.fetchall()]

    # ---------- التقارير ----------
    def add_report(self, path, content):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(
                f"INSERT INTO kidbook_reports (path, content) VALUES ({ph},{ph}) "
                f"RETURNING id", (path, content))
            row = cur.fetchone()
            return row["id"] if self.kind == "pg" else row[0]

    def list_reports(self, limit=50):
        with self._cur() as cur:
            cur.execute(f"SELECT * FROM kidbook_reports ORDER BY id DESC LIMIT {int(limit)}")
            return [dict(r) for r in cur.fetchall()]

    # ---------- الفرص ----------
    def add_opportunity(self, sector, title, niche, score, payload=None):
        ph = "%s" if self.kind == "pg" else "?"
        import json as _json
        with self._cur() as cur:
            cur.execute(
                f"INSERT INTO kidbook_opportunities (sector, title, niche, score, payload) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph}) RETURNING id",
                (sector, title, niche, float(score or 0),
                 _json.dumps(payload or {}, ensure_ascii=False)))
            row = cur.fetchone()
            return row["id"] if self.kind == "pg" else row[0]

    def list_opportunities(self, sector=None, status=None, limit=100):
        ph = "%s" if self.kind == "pg" else "?"
        q = "SELECT * FROM kidbook_opportunities"
        where, vals = [], []
        if sector:
            where.append(f"sector={ph}"); vals.append(sector)
        if status:
            where.append(f"status={ph}"); vals.append(status)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += f" ORDER BY id DESC LIMIT {int(limit)}"
        with self._cur() as cur:
            cur.execute(q, vals)
            return [dict(r) for r in cur.fetchall()]

    def decide_opportunity(self, opp_id, status, note=None):
        ph = "%s" if self.kind == "pg" else "?"
        if note is not None:
            with self._cur() as cur:
                cur.execute(
                    f"UPDATE kidbook_opportunities SET status={ph}, payload=COALESCE(payload,'') || {ph} WHERE id={ph}",
                    (status, f"\nnote: {note}", opp_id))
            return
        with self._cur() as cur:
            cur.execute(f"UPDATE kidbook_opportunities SET status={ph} WHERE id={ph}",
                        (status, opp_id))

    # ---------- الموافقات ----------
    def create_approval(self, kind, ref, note=None):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(
                f"INSERT INTO kidbook_approvals (kind, ref, note) VALUES ({ph},{ph},{ph}) RETURNING id",
                (kind, ref, note))
            row = cur.fetchone()
            return row["id"] if self.kind == "pg" else row[0]

    def decide_approval(self, approval_id, decision, note=None):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(
                f"UPDATE kidbook_approvals SET status={ph}, note=COALESCE({ph}, note), "
                f"decided_at=CURRENT_TIMESTAMP WHERE id={ph}",
                (decision, note, approval_id))

    def list_approvals(self, status=None, limit=100):
        ph = "%s" if self.kind == "pg" else "?"
        q = "SELECT * FROM kidbook_approvals"
        vals = []
        if status:
            q += f" WHERE status={ph}"; vals.append(status)
        q += f" ORDER BY id DESC LIMIT {int(limit)}"
        with self._cur() as cur:
            cur.execute(q, vals)
            return [dict(r) for r in cur.fetchall()]

    def get_approval(self, approval_id):
        ph = "%s" if self.kind == "pg" else "?"
        with self._cur() as cur:
            cur.execute(f"SELECT * FROM kidbook_approvals WHERE id={ph}", (approval_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    # ---------- إحصائيات للوحة التحكم ----------
    @staticmethod
    def _count(cur):
        row = cur.fetchone()
        if row is None:
            return 0
        if isinstance(row, dict):
            return int(next(iter(row.values())) or 0)
        return int(row[0])

    def stats(self):
        out = {"books": 0, "books_pdf_ready": 0, "books_published": 0,
               "runs": 0, "runs_failed": 0, "reports": 0,
               "opportunities": 0, "approvals_pending": 0}
        try:
            with self._cur() as cur:
                cur.execute("SELECT count(*) FROM kidbook_books")
                out["books"] = self._count(cur)
                cur.execute("SELECT count(*) FROM kidbook_books WHERE status IN ('pdf_ready','published')")
                out["books_pdf_ready"] = self._count(cur)
                cur.execute("SELECT count(*) FROM kidbook_books WHERE status='published'")
                out["books_published"] = self._count(cur)
                cur.execute("SELECT count(*) FROM kidbook_runs")
                out["runs"] = self._count(cur)
                cur.execute("SELECT count(*) FROM kidbook_runs WHERE status='failed'")
                out["runs_failed"] = self._count(cur)
                cur.execute("SELECT count(*) FROM kidbook_reports")
                out["reports"] = self._count(cur)
                cur.execute("SELECT count(*) FROM kidbook_opportunities")
                out["opportunities"] = self._count(cur)
                cur.execute("SELECT count(*) FROM kidbook_approvals WHERE status='pending'")
                out["approvals_pending"] = self._count(cur)
        except Exception:
            pass
        return out


def get_store() -> Store:
    global _store
    with _lock:
        if _store is None:
            _store = Store()
        return _store
