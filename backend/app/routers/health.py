"""Health route — open without a token. Exposes only {ok:true}; no host/user/DSN."""
from fastapi import APIRouter, Depends

from backend.app.auth import require_founder

from agents.capabilities.marketplace import etsy_config_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/admin/health")
def admin_health(_: str = Depends(require_founder)):
    """Full details — founder/admin only, never exposed without the token."""
    from backend.app.db import get_store
    from backend.app.services.store import counts
    from agents.llm import mode_label

    store = get_store()
    return {
        "ok": True, "version": "3.2.0",
        "db_backend": store.backend_label,
        "llm_mode": mode_label(),
        "etsy": etsy_config_status(),
        "counts": counts(),
    }
