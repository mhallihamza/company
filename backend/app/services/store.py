"""خدمات قاعدة البيانات — كل كتابات/قراءات الجدول من مكان واحد."""
from __future__ import annotations
import json
from typing import Any, Optional

from backend.app.db import get_store

_ph = "%s"  # pg placeholder — _execute يستبدلها تلقائياً لـ sqlite


# ---------------- تنفيذ عام ----------------
def q(sql: str, params: tuple = ()) -> list[dict]:
    return _store().q(sql, params)


def _store():
    return get_store()


def audit(task_id: int | None, actor: str, action: str, detail: str = "") -> bool:
    """يسجل في audit_logs — يستحوذ على فشل الكتابة دون كسر المسار."""
    try:
        get_store().audit(task_id, actor, action, detail)
        return True
    except Exception:  # noqa: BLE001
        return False

# ---------------- فرص ----------------
def add_opportunity(sector: str, title: str, niche: str, score: float,
                    payload: Optional[dict] = None, workspace: str = "default") -> int:
    s = _store()
    sql = "INSERT INTO opportunities (sector,title,niche,score,payload,workspace_id) VALUES (?,?,?,?,?,?) RETURNING opportunity_id".replace("?", "%s" if s.kind == "pg" else "?")
    with s._cur() as cur:  # noqa: SLF001
        cur.execute(sql, (sector, title, niche, float(score),
                          json.dumps(payload or {}, ensure_ascii=False), workspace))
        row = cur.fetchone()
        return int(row["opportunity_id"] if isinstance(row, dict) else row[0])


def list_opportunities(sector: str | None = None, status: str | None = None,
                       limit: int = 100, workspace: str = "default") -> list[dict]:
    s = _store()
    where, params = ["workspace_id=?"], [workspace]
    if sector:
        where.append("sector=?"); params.append(sector)
    if status:
        where.append("status=?"); params.append(status)
    sql = (f"SELECT * FROM opportunities WHERE {' AND '.join(where)} "
           f"ORDER BY opportunity_id DESC LIMIT {int(limit)}")
    return s.q(sql, tuple(params))


def set_opportunity_status(opp_id: int, status: str) -> bool:
    _execute_wrap("UPDATE opportunities SET status=? WHERE opportunity_id=?",
                  (status, opp_id))
    return True


# ---------------- منتجات ----------------
def upsert_product(slug: str, title: str, status: str | None = None,
                   pdf_path: str | None = None, cover_path: str | None = None,
                   final_file: str | None = None) -> int:
    s = _store()
    exists = s._scalar("SELECT count(*) FROM products WHERE slug=?".replace("?", "%s" if s.kind == "pg" else "?"), (slug,))
    if exists:
        sets, params = [], []
        for k, v in (("title", title), ("status", status), ("pdf_path", pdf_path),
                     ("cover_path", cover_path), ("final_file", final_file)):
            if v is not None:
                sets.append(f"{k}=?"); params.append(v)
        sets.append("updated_at=CURRENT_TIMESTAMP")
        _execute_wrap(f"UPDATE products SET {', '.join(sets)} WHERE slug=?",
                      tuple(params) + (slug,))
        return s._scalar("SELECT product_id FROM products WHERE slug=?".replace("?", "%s" if s.kind == "pg" else "?"), (slug,))
    _execute_wrap(
        "INSERT INTO products (slug,title,status,pdf_path,cover_path,final_file) VALUES (?,?,?,?,?,?)",
        (slug, title, status or "story", pdf_path, cover_path, final_file))
    return s.q("SELECT product_id FROM products WHERE slug=?".replace("?", "%s" if s.kind == "pg" else "?"),
               (slug,))[0]["product_id"]


def list_products(limit: int = 100, workspace: str = "default") -> list[dict]:
    return _store().q(
        f"SELECT * FROM products WHERE workspace_id=? ORDER BY product_id DESC LIMIT {int(limit)}",
        (workspace,))


def set_product_targets(slug: str, targets: list[str]) -> bool:
    """stores the publish targets for this product, as a JSON array"""
    import json as _json
    s = _store()
    sql = f"UPDATE products SET publish_targets=?, updated_at=CURRENT_TIMESTAMP WHERE slug=?"
    sql = sql.replace("?", "%s" if s.kind == "pg" else "?")
    with s._cur() as cur:  # noqa: SLF001
        cur.execute(sql, (_json.dumps(targets, ensure_ascii=False), slug))
    return True


def get_product(slug: str) -> dict[str, Any] | None:
    rows = _store().q("SELECT * FROM products WHERE slug=?", (slug,))
    return rows[0] if rows else None


# ---------------- تقارير ----------------
def add_report(path: str, title: str, content: str, kind: str = "md") -> int:
    s = _store()
    sql = "INSERT INTO reports (kind,path,title,content) VALUES (?,?,?,?) RETURNING report_id".replace(
        "?", "%s" if s.kind == "pg" else "?")
    with s._cur() as cur:  # noqa: SLF001
        cur.execute(sql, (kind, str(path)[:500], title[:200], content))
        row = cur.fetchone()
        return int(row["report_id"] if isinstance(row, dict) else row[0])


def list_reports(limit: int = 60, workspace: str = "default") -> list[dict]:
    return _store().q(
        f"SELECT * FROM reports WHERE workspace_id=? ORDER BY report_id DESC LIMIT {int(limit)}",
        (workspace,))


# ---------------- موافقات ----------------
def create_approval(kind: str, ref: str, note: str = "", workspace: str = "default") -> int:
    s = _store()
    sql = "INSERT INTO approvals (kind,ref,note,workspace_id) VALUES (?,?,?,?) RETURNING approval_id".replace(
        "?", "%s" if s.kind == "pg" else "?")
    with s._cur() as cur:  # noqa: SLF001
        cur.execute(sql, (kind, ref, note[:500], workspace))
        row = cur.fetchone()
        return int(row["approval_id"] if isinstance(row, dict) else row[0])


def list_approvals(status: str | None = None, limit: int = 60,
                   workspace: str = "default") -> list[dict]:
    where, params = ["workspace_id=?"], [workspace]
    if status:
        where.append("status=?"); params.append(status)
    return _store().q(
        f"SELECT * FROM approvals WHERE {' AND '.join(where)} "
        f"ORDER BY approval_id DESC LIMIT {int(limit)}", tuple(params))


def get_approval(aid: int) -> dict[str, Any] | None:
    rows = _store().q("SELECT * FROM approvals WHERE approval_id=?", (aid,))
    return rows[0] if rows else None


def decide_approval(aid: int, decision: str, note: str = "") -> bool:
    _execute_wrap(
        "UPDATE approvals SET status=?, note=COALESCE(NULLIF(?,''), note), decided_at=CURRENT_TIMESTAMP WHERE approval_id=?",
        (decision, note, aid))
    return True


# ---------------- مهام/تنفيذ ----------------
def create_task(task_type: str, domain: str, ref: str | None,
                input_text: str = "") -> int:
    return _store().create_task(task_type, domain, ref or "", input_text=input_text)


def finish_task(task_id: int, status: str, detail: str = "") -> None:
    _store().finish_task(task_id, status, detail)


def list_tasks(limit: int = 50, workspace: str = "default") -> list[dict]:
    return _store().q(
        f"SELECT * FROM tasks WHERE workspace_id=? ORDER BY task_id DESC LIMIT {int(limit)}",
        (workspace,))


def list_executions(limit: int = 50, workspace: str = "default") -> list[dict]:
    return _store().q(
        f"SELECT * FROM task_executions WHERE workspace_id=? ORDER BY exec_id DESC LIMIT {int(limit)}",
        (workspace,))


def create_execution(task_id: int, agent: str) -> int:
    return _store().create_execution(task_id, agent)


def finish_execution(exec_id: int, status: str, detail: str = "", tokens: int = 0) -> None:
    _store().finish_execution(exec_id, status, detail, tokens)


def list_audit(limit: int = 100, workspace: str = "default") -> list[dict]:
    return _store().q(
        f"SELECT * FROM audit_logs WHERE workspace_id=? ORDER BY log_id DESC LIMIT {int(limit)}",
        (workspace,))


# ---------------- إعدادات ----------------
def get_setting(key: str) -> str | None:
    rows = _store().q("SELECT value FROM settings WHERE key=?", (key,))
    return rows[0]["value"] if rows else None


def set_setting(key: str, value: str) -> None:
    s = _store()
    ph = "%s" if s.kind == "pg" else "?"
    _execute_wrap(
        f"INSERT INTO settings (key,value,updated_at) VALUES ({ph},{ph},CURRENT_TIMESTAMP) "
        f"ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
        (key, value))


def _execute_wrap(sql: str, params: tuple = ()) -> None:
    s = _store()
    sql = sql.replace("?", "%s") if s.kind == "pg" else sql
    with s._cur() as cur:  # noqa: SLF001
        cur.execute(sql, params)


# ---------------- حزمة / health ----------------
def counts() -> dict[str, int]:
    s = _store()
    def _scalar(sql: str) -> int:
        return s._scalar(sql.replace("?", "%s" if s.kind == "pg" else "?"))
    return {
        "tasks": _scalar("SELECT count(*) FROM tasks"),
        "executions": _scalar("SELECT count(*) FROM task_executions"),
        "opportunities": _scalar("SELECT count(*) FROM opportunities"),
        "products": _scalar("SELECT count(*) FROM products"),
        "products_pdf_ready": _scalar("SELECT count(*) FROM products WHERE status IN ('pdf','qa','approved','published')"),
        "products_published": _scalar("SELECT count(*) FROM products WHERE status='published'"),
        "reports": _scalar("SELECT count(*) FROM reports"),
        "approvals_pending": _scalar("SELECT count(*) FROM approvals WHERE status='pending'"),
    }
