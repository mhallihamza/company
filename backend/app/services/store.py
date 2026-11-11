"""Database services — all table writes/reads in one place."""
from __future__ import annotations
import json
from typing import Any, Optional

from backend.app.db import get_store

_ph = "%s"  # pg placeholder — _execute swaps it automatically for sqlite


# ---------------- general execution ----------------
def q(sql: str, params: tuple = ()) -> list[dict]:
    return _store().q(sql, params)


def _store():
    return get_store()


def audit(task_id: int | None, actor: str, action: str, detail: str = "") -> bool:
    """Log to audit_logs — swallows write failures without breaking the path."""
    try:
        get_store().audit(task_id, actor, action, detail)
        return True
    except Exception:  # noqa: BLE001
        return False

# ---------------- opportunities ----------------
def add_opportunity(sector: str, title: str, niche: str, score: float,
                    payload: Optional[dict] = None, workspace: str = "default",
                    source: str = "demo", evidence: Optional[dict] = None) -> int:
    s = _store()
    sql = ("INSERT INTO opportunities (sector,title,niche,score,payload,workspace_id,source,evidence) "
           "VALUES (?,?,?,?,?,?,?,?) RETURNING opportunity_id").replace(
        "?", "%s" if s.kind == "pg" else "?")
    with s._cur() as cur:  # noqa: SLF001
        cur.execute(sql, (sector, title[:500], niche[:80], float(score),
                          json.dumps(payload or {}, ensure_ascii=False), workspace,
                          source, json.dumps(evidence or {}, ensure_ascii=False)))
        row = cur.fetchone()
        return int(row["opportunity_id"] if isinstance(row, dict) else row[0])


def clamp_score(x: float | int | str | None) -> float:
    try:
        f = float(x)  # noqa: F841
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, round(f, 2)))


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


# ---------------- products ----------------
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


# ---------------- reports ----------------
def add_report(path: str, title: str, content: str, kind: str = "md",
               source: str = "demo", evidence: Optional[dict] = None) -> int:
    s = _store()
    sql = ("INSERT INTO reports (kind,path,title,content,source,evidence) "
           "VALUES (?,?,?,?,?,?) RETURNING report_id").replace(
        "?", "%s" if s.kind == "pg" else "?")
    with s._cur() as cur:  # noqa: SLF001
        cur.execute(sql, (kind, str(path)[:500], title[:200], content,
                          source, json.dumps(evidence or {}, ensure_ascii=False)))
        row = cur.fetchone()
        return int(row["report_id"] if isinstance(row, dict) else row[0])


def list_reports(limit: int = 60, workspace: str = "default") -> list[dict]:
    return _store().q(
        f"SELECT * FROM reports WHERE workspace_id=? ORDER BY report_id DESC LIMIT {int(limit)}",
        (workspace,))


# ---------------- approvals ----------------
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


# ---------------- tasks/executions ----------------
def create_task(task_type: str, domain: str, ref: str | None,
                input_text: str = "") -> int:
    s = _store()
    # enforce a simple monthly USD budget — blocks runaway spend
    rows = s.q("SELECT monthly_limit_usd, used_usd FROM budgets WHERE workspace_id=?",
               ("default",))
    if rows:
        b = rows[0]
        limit_ = float(b.get("monthly_limit_usd") or 0)
        used = float(b.get("used_usd") or 0.0)
        if limit_ > 0 and used >= limit_:
            raise RuntimeError(
                f"Monthly budget exhausted: ${used:.2f} / ${limit_:.2f} — refusing new task.")
    return _store().create_task(task_type, domain, ref or "", input_text=input_text)


def finish_task(task_id: int, status: str, detail: str = "") -> None:
    _store().finish_task(task_id, status, detail)
    # $0.15 flat charge per finished task — honest placeholder, enforced by the limit check above
    try:
        _execute_wrap("UPDATE budgets SET used_usd = used_usd + 0.15 WHERE workspace_id=?",
                      ("default",))
    except Exception:  # noqa: BLE001
        pass  # budget update is best-effort


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


def finish_execution(exec_id: int, status: str, detail: str = "", tokens: int | None = None) -> None:
    _store().finish_execution(exec_id, status, detail, tokens)


def list_audit(limit: int = 100, workspace: str = "default") -> list[dict]:
    return _store().q(
        f"SELECT * FROM audit_logs WHERE workspace_id=? ORDER BY log_id DESC LIMIT {int(limit)}",
        (workspace,))


# ---------------- settings ----------------
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


# ---------------- bundle / health ----------------
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
        "research_runs": _scalar("SELECT count(*) FROM research_runs"),
    }


# ---------------- research runs / competitor observations ----------------

def create_research_run(query: str, task_id: int | None = None, workspace: str = "default") -> int:
    s = _store()
    s._execute("INSERT INTO research_runs (workspace_id, query, task_id) VALUES (?,?,?)",
               (workspace, query, task_id))
    with s._cur() as cur:
        if s.kind == "pg":
            cur.execute("SELECT LASTVAL()")
        else:
            cur.execute("SELECT last_insert_rowid()")
        row = cur.fetchone()
        return int(row[0] if not isinstance(row, dict) else row["lastval"])


def add_research_source(run_id: int, source: str, query: str, collected_at: str | None,
                        verified: bool, blind_spot: bool, workspace: str = "default") -> None:
    _store()._execute(
        "INSERT INTO research_sources (run_id, workspace_id, source, query, collected_at, verified, blind_spot) "
        "VALUES (?,?,?,?,?,?,?)",
        (run_id, workspace, source, query, collected_at, bool(verified), bool(blind_spot)))


def add_competitor_observation(run_id: int, rec: dict, workspace: str = "default") -> None:
    import json as _json
    raw = rec.get("raw") if isinstance(rec.get("raw"), dict) else {}
    _store()._execute(
        "INSERT INTO competitor_observations "
        "(run_id, workspace_id, source, market, data_type, title, url, price, rating, reviews, captured_at, verified, raw) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, workspace, str(rec.get("source") or ""), str(rec.get("market") or ""),
         str(rec.get("data_type") or ""), str(rec.get("title") or ""), str(rec.get("url") or ""),
         rec.get("price"), rec.get("rating"), rec.get("reviews"),
         str(rec.get("captured_at") or ""), bool(rec.get("verified")),
         _json.dumps(raw, ensure_ascii=False)))


def list_competitor_observations(run_id: int, limit: int = 100, workspace: str = "default") -> list[dict]:
    limit = max(1, min(int(limit), 500))
    ph = "?" if _store().kind == "sqlite" else "%s"
    return q(f"SELECT * FROM competitor_observations WHERE run_id={ph} AND workspace_id='{workspace}' "
             "ORDER BY observation_id DESC LIMIT %d" % limit, (run_id,))


# ---------------- product briefs / assets / QA reports ----------------

def upsert_product_brief(product_key: str, content: dict, workspace: str = "default") -> int:
    import json as _json
    s = _store()
    title = str(content.get("title") or product_key)
    try:
        s._execute(
            "INSERT INTO product_briefs (workspace_id, product_key, title, target_age, format, page_count, marketplace, content, status) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (product_key) DO UPDATE SET title=EXCLUDED.title, target_age=EXCLUDED.target_age, "
            "format=EXCLUDED.format, page_count=EXCLUDED.page_count, marketplace=EXCLUDED.marketplace, "
            "content=EXCLUDED.content, updated_at=CURRENT_TIMESTAMP",
            (workspace, product_key, title, str(content.get("target_age") or "3-5"),
             str(content.get("format") or "picture_book"),
             int(content.get("page_count") or 12),
             str(content.get("marketplace") or "kdp"),
             _json.dumps(content, ensure_ascii=False),
             str(content.get("status") or "pending_approval")))
    except Exception as e:  # noqa: BLE001
        # sqlite doesn't support ON CONFLICT for this shape — do a manual upsert
        rows = q("SELECT brief_id FROM product_briefs WHERE product_key=?", (product_key,))
        if rows:
            s._execute("UPDATE product_briefs SET title=?, target_age=?, format=?, page_count=?, marketplace=?, content=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE product_key=?",
                       (title, str(content.get("target_age") or "3-5"),
                        str(content.get("format") or "picture_book"),
                        int(content.get("page_count") or 12),
                        str(content.get("marketplace") or "kdp"),
                        _json.dumps(content, ensure_ascii=False),
                        str(content.get("status") or "pending_approval"), product_key))
        else:
            s._execute("INSERT INTO product_briefs (workspace_id, product_key, title, target_age, format, page_count, marketplace, content, status) VALUES (?,?,?,?,?,?,?,?,?)",
                       (workspace, product_key, title, str(content.get("target_age") or "3-5"),
                        str(content.get("format") or "picture_book"),
                        int(content.get("page_count") or 12),
                        str(content.get("marketplace") or "kdp"),
                        _json.dumps(content, ensure_ascii=False),
                        str(content.get("status") or "pending_approval")))
    with s._cur() as cur:
        if s.kind == "pg":
            cur.execute("SELECT brief_id FROM product_briefs WHERE product_key=%s", (product_key,))
        else:
            cur.execute("SELECT brief_id FROM product_briefs WHERE product_key=?", (product_key,))
        row = cur.fetchone()
        return int(row["brief_id"] if isinstance(row, dict) else row[0])


def get_product_brief(product_key: str) -> dict | None:
    rows = q("SELECT * FROM product_briefs WHERE product_key=?", (product_key,))
    if not rows:
        return None
    row = rows[0]
    row["content"] = json.loads(row["content"]) if isinstance(row.get("content"), str) else row.get("content")
    return row


def add_generated_asset(product_key: str, page_number: int | None, asset_type: str,
                        path: str, provider: str | None = None, style: str | None = None,
                        workspace: str = "default") -> int:
    s = _store()
    s._execute(
        "INSERT INTO generated_assets (workspace_id, product_key, page_number, asset_type, path, provider, style) "
        "VALUES (?,?,?,?,?,?,?)",
        (workspace, product_key, page_number, asset_type, path, provider, style))
    with s._cur() as cur:
        if s.kind == "pg":
            cur.execute("SELECT LASTVAL()")
            row = cur.fetchone()
            return int(row["lastval"] if isinstance(row, dict) else row[0])
        cur.execute("SELECT last_insert_rowid()")
        row = cur.fetchone()
        return int(row[0])


def list_generated_assets(product_key: str, workspace: str = "default") -> list[dict]:
    return q("SELECT * FROM generated_assets WHERE product_key=? AND workspace_id=? ORDER BY page_number",
             (product_key, workspace))


def add_qa_report(product_key: str, verdict: str, checks: dict, workspace: str = "default") -> int:
    import json as _json
    s = _store()
    s._execute("INSERT INTO qa_reports (workspace_id, product_key, verdict, checks) VALUES (?,?,?,?)",
               (workspace, product_key, verdict, _json.dumps(checks, ensure_ascii=False)))
    with s._cur() as cur:
        if s.kind == "pg":
            cur.execute("SELECT LASTVAL()")
            row = cur.fetchone()
            return int(row["lastval"] if isinstance(row, dict) else row[0])
        cur.execute("SELECT last_insert_rowid()")
        row = cur.fetchone()
        return int(row[0])


def list_qa_reports(product_key: str, workspace: str = "default") -> list[dict]:
    rows = q("SELECT * FROM qa_reports WHERE product_key=? AND workspace_id=? ORDER BY qa_id DESC",
             (product_key, workspace))
    for r in rows:
        try:
            r["checks"] = json.loads(r["checks"]) if isinstance(r["checks"], str) else r["checks"]
        except Exception:  # noqa: BLE001
            pass
    return rows


def upsert_listing_draft(product_key: str, marketplace: str, title: str,
                         description: str, tags: str, price: float | None,
                         workspace: str = "default", status: str = "pending_approval") -> int:
    import json as _json
    s = _store()
    s._execute(
        "INSERT INTO marketplace_listing_drafts (workspace_id, product_key, marketplace, title, description, tags, price, status) "
        "VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT DO NOTHING",
        (workspace, product_key, marketplace, title, description, tags, price, status))
    rows = q("SELECT draft_id FROM marketplace_listing_drafts WHERE product_key=? AND marketplace=?",
             (product_key, marketplace))
    if rows:
        return int(rows[0]["draft_id"])
    # sqlite has no ON CONFLICT with this shape; just re-insert
    s._execute("INSERT INTO marketplace_listing_drafts (workspace_id, product_key, marketplace, title, description, tags, price, status) "
               "VALUES (?,?,?,?,?,?,?,?)",
               (workspace, product_key, marketplace, title, description, tags, price, status))
    rows = q("SELECT draft_id FROM marketplace_listing_drafts WHERE product_key=? AND marketplace=? ORDER BY draft_id DESC LIMIT 1",
             (product_key, marketplace))
    return int(rows[0]["draft_id"]) if rows else -1


def list_listing_drafts(product_key: str, workspace: str = "default") -> list[dict]:
    return q("SELECT * FROM marketplace_listing_drafts WHERE product_key=? AND workspace_id=? ORDER BY created_at",
             (product_key, workspace))
