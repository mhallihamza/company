"""واجهة الـ CEO — POST /api/ceo/run + سجل التدقيق.

ملاحظة أمنية: `human_confirmed` في جسم الطلب **لا يُوثق**. كل نشر حقيقي يجب
أن يمر عبر approval row حقيقي بحالة `approved` وref مطابق للـ slug.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from agents.ceo.graph import run_task
from backend.app.auth import require_founder
from backend.app.services import store as svc

router = APIRouter(tags=["ceo"], dependencies=[Depends(require_founder)])


class CeoRunIn(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000)
    workspace: str = "default"


@router.post("/ceo/run")
def ceo_run(body: CeoRunIn):
    return run_task(body.task, workspace=body.workspace, human_confirmed=False)


@router.get("/audit")
def audit(limit: int = 80):
    limit = max(1, min(int(limit), 500))   # cap the readout
    return svc.list_audit(limit=limit)
