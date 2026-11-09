"""المسار الصحي — مفتوح بلا رمز."""
from fastapi import APIRouter

from backend.app import config
from backend.app.db import get_store
from backend.app.services.store import counts
from agents.llm import mode_label

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    store = get_store()
    return {"ok": True,
            "version": "3.0.0",
            "db_backend": store.backend_label,
            "db_diag": store.pg_diag,
            "llm_mode": mode_label(),
            "storage": str(config.STORAGE),
            "counts": counts()}
