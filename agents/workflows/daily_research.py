"""workflow daily_research — morning opportunity scan (triggered by the 08:00 scheduler or on demand)."""
from __future__ import annotations

from datetime import datetime

from agents.registry import DEPARTMENTS
from backend.app.services import store as svc


def run() -> dict:
    started = datetime.now().isoformat(timespec="seconds")
    results = []
    for key in ("intelligence", "affiliate"):
        spec = DEPARTMENTS.get(key)
        if spec:
            out = spec.run("morning auto scan", task_id=None)
            results.append({"department": key, "ok": out.get("ok"), "summary": out.get("summary")})
    svc.audit(None, "scheduler", "daily_research",
              f"{len(results)} department(s) finished")
    return {"started": started, "finished": datetime.now().isoformat(timespec="seconds"),
            "results": results}
