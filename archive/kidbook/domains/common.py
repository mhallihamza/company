"""أدوات مشتركة لكل الأقسام: الحالة، المشرف، التسجيل، والأخطاء."""
from __future__ import annotations
import json
import re
from typing import TypedDict

from langchain_core.messages import SystemMessage, HumanMessage

from kidbook.db import get_store
from kidbook.llm import get_chat_model


class KidState(TypedDict, total=False):
    task: str
    idea: str
    slug: str
    language: str
    stop_after: str
    progress: list[str]
    story: dict
    research: dict
    pdf_path: str
    artifacts: dict
    human_confirmed: bool
    run_id: int
    error: str
    summary: str


def log(store, run_id, msg, level="info"):
    if run_id:
        store.log(run_id, msg, level)


def slugify(text: str) -> str:
    slug = re.sub(r"\W+", "_", text, flags=re.UNICODE).strip("_")[:40]
    return slug or f"item_{abs(hash(text)) % 10**8}"


def invoke_domain(graph, state, store, run_id, label):
    result = graph.invoke(state, config={"recursion_limit": 12})
    if result.get("error"):
        log(store, run_id, result["error"], "error")
        store.finish_run(run_id, "failed", result["error"])
        raise DomainError(result["error"])
    store.finish_run(run_id, "success", result.get("summary") or label)
    return result


def ask_supervisor(role: str, markers: list[str],
                   options: list[tuple[str, str | None]]) -> str:
    """يسأل المشرف أي عقدة التالي مع سقوط حتمي عند أي غموض."""
    prefixes = {m.split(" ", 1)[0] for m in markers}

    def heuristic() -> str:
        for value, done_prefix in options:
            if done_prefix is None or done_prefix not in prefixes:
                return value
        return "done"

    try:
        model = get_chat_model(temperature=0, max_tokens=200)
        valid = [v for v, _ in options]
        sys = (f"[ROLE:{role}]\nYou are a supervisor routing between worker agents.\n"
               f"Completed so far: {markers or ['nothing']}\n"
               f"Allowed next values: {valid}\n"
               f'Reply ONLY JSON: {{"next": "<one of the allowed values>"}}')
        raw = model.invoke([SystemMessage(content=sys),
                            HumanMessage(content="Decide the next step.")]).content
        match = re.search(r"\{.*?\}", str(raw), re.S)
        if not match:
            return heuristic()
        nxt = str(json.loads(match.group(0))["next"]).strip().lower()
        return nxt if nxt in valid else heuristic()
    except Exception:  # noqa: BLE001
        return heuristic()


class DomainError(RuntimeError):
    pass


def get_or_create_store():
    return get_store()
