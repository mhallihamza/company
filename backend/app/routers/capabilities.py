"""القدرات — جميع القدرات المشتركة المسجلة مع مستعمليها."""
from fastapi import APIRouter, Depends

from agents.capabilities import list_capabilities
from backend.app.auth import require_founder

router = APIRouter(tags=["capabilities"], dependencies=[Depends(require_founder)])


@router.get("/capabilities")
def capabilities():
    return [c.to_public() for c in list_capabilities()]
