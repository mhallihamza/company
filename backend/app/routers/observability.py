"""Observability — company metrics from reality (not from the model).

Everything is read from the tasks/task_executions/approvals/audit_logs tables:
no intelligence here, just accurate aggregation.
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
    # per department/agent: total + success + failure + tokens (measured only — unmeasured stays NULL)
    by_agent = s.q(
        "SELECT agent, COUNT(*) AS executions, "
        "COUNT(tokens_used) AS executions_with_token_data, "
        "SUM(tokens_used) AS tokens_measured, "
        "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, "
        "SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS failed "
        "FROM task_executions GROUP BY agent ORDER BY executions DESC")
    for row in by_agent:
        row["token_source"] = "measured" if int(row.get("executions_with_token_data") or 0) > 0 else "unmeasured"
        row["tokens_used"] = row.get("tokens_measured") or 0
    by_domain = s.q(
        "SELECT domain, COUNT(*) AS total, "
        "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, "
        "SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS failed, "
        "MAX(finished_at) AS last_finished "
        "FROM tasks GROUP BY domain ORDER BY total DESC")
    total_executions = sum(int(a.get("executions") or 0) for a in by_agent)
    measured_executions = sum(int(a.get("executions_with_token_data") or 0) for a in by_agent)
    total_tokens = sum(int(a.get("tokens_measured") or 0) for a in by_agent)
    # budget estimate: flat $0.15 per task (fixed in the budget) — not a provider-measured figure
    budget_estimate_usd = round(total_executions * 0.15, 4)
    tokens_source = ("measured" if measured_executions == total_executions and total_executions
                     else "unmeasured" if measured_executions == 0
                     else "measured+unmeasured")

    # approval outcomes
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
        "tokens_measured_total": total_tokens,
        "executions_with_token_data": measured_executions,
        "executions_unmeasured": max(0, total_executions - measured_executions),
        "tokens_source": tokens_source,
        "budget_estimate_usd": budget_estimate_usd,
        "budget_note": "flat $0.15 per finished task — estimated, not provider-measured",
        "recent_tasks": svc.list_tasks(limit=8),
        "audit": svc.list_audit(limit=15),
    }
