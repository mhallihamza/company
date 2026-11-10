"""Opportunities — list and status changes + registration skills."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth import require_founder
from backend.app.services import store as svc

router = APIRouter(tags=["opportunities"], dependencies=[Depends(require_founder)])


class StatusIn(BaseModel):
    status: str


@router.get("/opportunities")
def list_opps(sector: str | None = None, status: str | None = None, limit: int = 100):
    return svc.list_opportunities(sector=sector, status=status, limit=limit)


@router.patch("/opportunities/{opp_id}/status")
def set_status(opp_id: int, body: StatusIn):
    if body.status not in ("new", "watching", "pursuing", "archived"):
        raise HTTPException(422, "unknown status")
    svc.set_opportunity_status(opp_id, body.status)
    return {"ok": True, "opportunity_id": opp_id, "status": body.status}
