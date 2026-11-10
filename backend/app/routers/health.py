"""المسار الصحي — مفتوح بلا رمز. يكشف فقط {ok:true}؛ لا host/user/DSN."""
from fastapi import APIRouter, Depends

from backend.app.auth import require_founder

from agents.capabilities.marketplace import etsy_config_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/admin/health")
def admin_health(_: str = Depends(require_founder)):
    """كامل التفاصيل — للمالك/الأدمن فقط، لا تكشف بدون الرمز."""
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
