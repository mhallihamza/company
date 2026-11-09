"""opportunity_validation — يضبط الفرص الجديدة إلى pursuing/archived بدرجة الحد."""
from __future__ import annotations

import json

from backend.app.services import store as svc

MIN_SCORE = 6.5


def run(limit: int = 20) -> dict:
    rows = svc.list_opportunities(status="new", limit=limit)
    promoted = archived = 0
    for opp in rows:
        score = float(opp.get("score") or 0)
        payload = opp.get("payload") or "{}"
        try:
            meta = json.loads(payload) if isinstance(payload, str) else payload
        except Exception:  # noqa: BLE001
            meta = {}
        if score >= MIN_SCORE:
            svc.set_opportunity_status(opp["opportunity_id"], "pursuing")
            promoted += 1
            svc.upsert_product(f"opp_{opp['opportunity_id']}", opp.get("title", "مرشح"),
                               status="candidate")
        else:
            svc.set_opportunity_status(opp["opportunity_id"], "archived")
            archived += 1
    svc.audit(None, "workflow", "opportunity_validation",
              f"promoted={promoted} archived={archived}")
    return {"reviewed": len(rows), "promoted": promoted, "archived": archived}
