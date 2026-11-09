"""Observability — مقاييس مراقبة الشركة من الواقع (وليس من النموذج).

كل شيء يُقرأ من جداول tasks/task_executions/approvals/audit_logs:
لا يوجد ذكاء هنا، فقط جمع دقيق.
"""
from fastapi import APIRouter, Depends

from backend.app import config
from backend.app.auth import require_founder
from backend.app.db import get_store
from backend.app.services import store as svc
from agents.llm import mode_label

router = APIRouter(tags=["observability"], dependencies=[Depends(require_founder)])


@router.get("/observability")
def observability():
    s = get_store()
    # بكل قسم/وكيل: إجمالي + نجاح + فشل + رموز مستهلكة
    by_agent = s.q(
        "SELECT agent, COUNT(*) AS executions, "
        "COALESCE(SUM(tokens_used), 0) AS tokens_used, "
        "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, "
        "SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS failed "
        "FROM task_executions GROUP BY agent ORDER BY executions DESC")
    by_domain = s.q(
        "SELECT domain, COUNT(*) AS total, "
        "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, "
        "SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS failed, "
        "MAX(finished_at) AS last_finished "
        "FROM tasks GROUP BY domain ORDER BY total DESC")
    total_tokens = sum(int(a.get("tokens_used") or 0) for a in by_agent)

    # نتائج الموافقات
    approvals = {r["status"]: int(r["n"]) for r in s.q(
        "SELECT status, COUNT(*) AS n FROM approvals GROUP BY status")}
    approvals_summary = {
        "pending": approvals.get("pending", 0),
        "approved": approvals.get("approved", 0),
        "rejected": approvals.get("rejected", 0),
    }

    return {
        "llm_mode": mode_label(),
        "db_backend": s.backend_label,
        "db_diag": s.pg_diag or "",
        "storage": str(config.STORAGE),
        "counts": svc.counts(),
        "executions_by_agent": by_agent,
        "tasks_by_domain": by_domain,
        "approvals": approvals_summary,
        "tokens_total": total_tokens,
        "recent_tasks": svc.list_tasks(limit=8),
        "audit": svc.list_audit(limit=15),
    }
