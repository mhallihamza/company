"""Approvals — the human-judgment gate before any publish."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.auth import require_founder
from backend.app.services import store as svc
from agents.workflows import publishing as publishing_workflow
from agents.departments.books import publishing as publishing_dept

router = APIRouter(tags=["approvals"], dependencies=[Depends(require_founder)])


class DecideIn(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    note: str = Field("", max_length=500)


@router.get("/approvals")
def list_approvals(status: str | None = None, limit: int = 60):
    return svc.list_approvals(status=status, limit=limit)


@router.post("/approvals/{approval_id}/decide")
def decide_approval(approval_id: int, body: DecideIn):
    approval = svc.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, f"no approval request #{approval_id}")
    if approval["status"] != "pending":
        raise HTTPException(409, f"request #{approval_id} already decided ({approval['status']})")

    svc.decide_approval(approval_id, "approved" if body.decision == "approve" else "rejected",
                        body.note)
    svc.audit(None, "human", f"decision:{body.decision}",
              f"approval={approval_id} note={body.note[:80]}")

    if body.decision == "reject":
        return {"ok": True, "approval_id": approval_id, "decision": "rejected"}

    # run publishing only after the approved decision
    out = publishing_workflow.run(approval_id)
    if out.get("ok"):
        return {"ok": True, "approval_id": approval_id, "decision": "approved",
                "listing_id": out.get("listing_id"), "mock": out.get("mock", True),
                "summary": out.get("summary")}
    # approved decision, but execution failed — surface the reason plainly
    raise HTTPException(502, f"approved but execution failed: {out.get('error')}")
