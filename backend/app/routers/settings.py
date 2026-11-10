"""Settings — redacted general info (no secrets) + autonomy level."""
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.auth import require_founder
from backend.app.services import store as svc
from agents.llm import mode_label
from agents.capabilities.marketplace import etsy_config_status

router = APIRouter(tags=["settings"], dependencies=[Depends(require_founder)])

AUTONOMY_LEVELS = [
    {"level": 1, "name": "Research", "describe": "Search, analysis and reports — everything waits for your approval."},
    {"level": 2, "name": "Production", "describe": "Books, designs and GTM packs — autonomous internally."},
    {"level": 3, "name": "Gated publishing", "describe": "Publishing with declared approval + full audit trail."},
]


class AutonomyIn(BaseModel):
    level: int


def _redact(v: str) -> str:
    if not v:
        return "—"
    return v[:4] + "…" + v[-2:] if len(v) > 8 else "set"


@router.get("/settings")
def settings():
    ext = etsy_config_status()
    return {
        "llm_mode": mode_label(),
        "db_backend": os.getenv("DB_BACKEND", "auto"),
        "autonomy_level": int(svc.get_setting("autonomy_level") or 1),
        "autonomy_levels": AUTONOMY_LEVELS,
        "keys": {
            "MISTRAL_API_KEY": _redact(os.getenv("MISTRAL_API_KEY", "")),
            "DATABASE_URL": "set" if os.getenv("DATABASE_URL") else "not set",
            "FOUNDER_TOKEN": _redact(os.getenv("FOUNDER_TOKEN", "")),
        },
        "etsy": {
            "status": "configured" if ext["etsy_configured"] else "not_configured",
            "variables": ext,
        },
        "scheduler_enabled": os.getenv("ENABLE_SCHEDULER", "").lower() in ("1", "true", "yes"),
    }


@router.post("/settings/autonomy")
def set_autonomy(body: AutonomyIn):
    if body.level not in (1, 2, 3):
        from fastapi import HTTPException
        raise HTTPException(422, "autonomy level must be 1, 2 or 3")
    svc.set_setting("autonomy_level", str(body.level))
    svc.audit(None, "founder", "set_autonomy", f"level={body.level}")
    return {"ok": True, "autonomy_level": body.level}
