"""الوكلاء — بطاقات الـ Agent Cards (كلها ظاهرة من السجل)."""
from typing import Any

from fastapi import APIRouter, Depends

from agents import registry
from backend.app.auth import require_founder

router = APIRouter(tags=["agents"], dependencies=[Depends(require_founder)])


@router.get("/agents")
def list_agent_cards():
    return registry.list_agents()
