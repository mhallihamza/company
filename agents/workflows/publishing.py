"""publishing — post-approval publishing gate: executes what the board approved."""
from __future__ import annotations

from agents.departments.books import publishing
from backend.app.services import store as svc


def run(approval_id: int) -> dict:
    approval = svc.get_approval(approval_id)
    if not approval:
        return {"ok": False, "error": f"No approval decision #{approval_id}"}
    if approval["status"] != "approved":
        return {"ok": False, "error": f"Approval #{approval_id} not approved (status: {approval['status']})"}
    slug = approval["ref"]
    out = publishing.run(slug, slug=slug, human_confirmed=True)
    svc.audit(None, "workflow", "publishing",
              f"approval={approval_id} slug={slug} ok={out.get('ok')}")
    return out
