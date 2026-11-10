"""أدوات مشتركة لكل الأقسام: الحالة، مشرف حتمي مع سقوط للنموذج، ورفع التقارير.
"""
from __future__ import annotations
import json
import re
from typing import Any, Callable, TypedDict
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage


class HQState(TypedDict, total=False):
    task: str
    idea: str
    slug: str
    language: str
    stop_after: str
    progress: list[str]
    story: dict
    research: dict
    artifacts: dict
    summary: str
    error: str
    run_id: int | None
    human_confirmed: bool
    text_direction: str
    font_ref: str
    market: str
    market_profile: dict
    fee_source: str


def regex_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("The model did not return valid JSON")
    return json.loads(match.group(0))


def deterministic_supervisor(options: list[str], completions: list[str], state_progress: list[str]) -> str:
    """يطابق بقية الإنجاز حسب الحالة؛ يُستخدم عند غياب النموذج أو غموضه."""
    done = {p.split(" ", 1)[0] for p in state_progress}
    for value in options:
        if value == "done":
            continue
        marker = value.split("→")[-1] if "→" in value else value.upper() + "_DONE"
        if marker not in done:
            return value
    return "done"


def ask_supervisor(role: str, options: list[str], state_progress: list[str]) -> str:
    """يوجه المشرف: نموذج لغوي في الوضع الحي، خوارزمية حتمية في الوضع التجريبي وعند أي فشل."""
    from agents.llm import get_chat_model

    prefixes = {m.split(" ", 1)[0] for m in state_progress}

    def heuristic() -> str:
        return deterministic_supervisor(options[:-1] if options and options[-1] == "done" else options, [], []) \
            if False else _heuristic(options, prefixes)

    try:
        model = get_chat_model(temperature=0, max_tokens=150)
        sys = (f"[ROLE:{role}]\nYou are a supervisor routing its department.\n"
               f"Completed: {state_progress or ['nothing']}\nAllowed: {options}\n"
               'Reply ONLY JSON {"next": "<one of allowed>"}')
        raw = model.invoke([SystemMessage(content=sys), HumanMessage(content="Decide")]).content
        nxt = str(regex_json(str(raw)).get("next", "")).strip().lower()
        return nxt if nxt in options else _heuristic(options, prefixes)
    except Exception:  # noqa: BLE001 — لا نكسر المستخدم لأن النموذج فشل
        return _heuristic(options, prefixes)


def _heuristic(options: list[str], prefixes: set[str]) -> str:
    for value in options:
        if value == "done":
            continue
        marker = value.upper().replace("-", "_").replace(" ", "_") + "_DONE"
        if marker not in prefixes:
            return value
    return "done" if "done" in options else options[-1]


def log_to_db(task_id: int | None, actor: str, action: str, detail: str = ""):
    """يسجل في جدول audit_logs دون كسر أي مسار رئيسي."""
    try:
        from backend.app import db  # noqa: PLC0415
        db.audit(task_id=task_id, actor=actor, action=action, detail=detail[:2000])
    except Exception:  # noqa: BLE001
        pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
