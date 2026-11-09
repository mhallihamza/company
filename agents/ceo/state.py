"""CEO state — الحالة المشتركة بين عقد الـ CEO (LangGraph)."""
from __future__ import annotations
from typing import TypedDict


class CEOState(TypedDict, total=False):
    task: str
    workspace: str
    task_id: int
    domain: str
    artifacts: dict
    summary: str
    error: str
    needs_approval: bool
    human_confirmed: bool
    exec_id: int
