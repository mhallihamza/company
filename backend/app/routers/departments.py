"""سجل الأقسام — عرض وتشغيل + مهام تنفيذية."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agents import registry
from backend.app.auth import require_founder
from backend.app.services import store as svc

router = APIRouter(tags=["departments"], dependencies=[Depends(require_founder)])


class RunIn(BaseModel):
    task: str = Field("", max_length=2000)
    human_confirmed: bool = False   # kept for Wire compatibility — never trusted


@router.get("/departments")
def list_depts():
    return [spec.to_public() for spec in registry.list_departments()]


@router.get("/departments/{key}")
def get_dept(key: str):
    spec = registry.get_department(key)
    if not spec:
        raise HTTPException(404, f"no department registered named {key}")
    return spec.to_public()


@router.post("/departments/{key}/run")
def run_dept(key: str, body: RunIn):
    spec = registry.get_department(key)
    if not spec:
        raise HTTPException(404, f"no department registered named {key}")
    task_id = svc.create_task("manual", key, ref=(body.task or key)[:200],
                              input_text=body.task)
    exec_id = svc.create_execution(task_id, key)
    kwargs = {"task": body.task or "", "task_id": task_id}
    if spec.approval_policy == "human_required":
        ref = (body.task or key).split()[-1] if body.task else key
        kwargs["human_confirmed"] = _approved_ref_exists(ref)
    try:
        out = spec.run(**kwargs)
    except Exception as e:  # noqa: BLE001
        svc.finish_task(task_id, "failed", str(e)[:800])
        svc.finish_execution(exec_id, "failed", str(e)[:400])
        raise HTTPException(500, f"department failed: {e}") from e
    ok = bool(out.get("ok"))
    svc.finish_task(task_id, "success" if ok else "failed",
                    (out.get("summary") or out.get("error") or "")[:400])
    svc.finish_execution(exec_id, "success" if ok else "failed",
                         str(out.get("summary") or out.get("error") or "")[:400],
                         int(out.get("tokens_used", 0) or 0))
    return out


@router.get("/tasks")
def tasks(limit: int = 50):
    limit = max(1, min(int(limit), 200))
    return svc.list_tasks(limit=limit)


@router.get("/executions")
def executions(limit: int = 50):
    limit = max(1, min(int(limit), 200))
    return svc.list_executions(limit=limit)


def _approved_ref_exists(ref: str) -> bool:
    """Only trust an approval record that actually exists and is approved (server-side check)."""
    try:
        rows = svc.list_approvals(status="approved", limit=100)
        return any((str(r.get("ref", "")) == ref) for r in rows)
    except Exception:  # noqa: BLE001
        return False
