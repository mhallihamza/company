"""CEO graph — the central commander: plan → execute exchange → evaluate → close.

Executes deterministic routing first, falling back to the model when that is not enough:
  plan → route (keyword/LLM from the registry) → execute (department) → evaluate (verdict) → close
This flow is orchestrated (LangGraph), not a hardcoded call chain, so that later we can
add Kill Switches/Human Loops per node.
"""
from __future__ import annotations
import json
import re
from typing import Any

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState  # noqa: F401 — kept for future inheritance
from agents.ceo.state import CEOState
from agents.llm import get_chat_model, llm_last_note
from agents.registry import DEPARTMENTS, list_departments
from backend.app import db as _db
from backend.app.services import store as svc


def _keyword_pick(text: str) -> str | None:
    from agents.ceo.routing import route_keywords
    return route_keywords(text).get("department")


def _autonomy_allowed(level: int, key: str) -> bool:
    from backend.app.services.autonomy import department_allowed
    return department_allowed(level, key)


def route_task(task: str) -> str:
    """Route a task to one department — LLM with keyword fallback; no guess on ambiguity."""
    from agents.ceo.routing import route_keywords, route_llm
    out = route_llm(task)
    dept = out.get("department")
    if dept in DEPARTMENTS:
        return dept
    fallback = route_keywords(task)
    fallback_dept = fallback.get("department")
    return fallback_dept if fallback_dept in DEPARTMENTS else "books.content"


# ---------------- CEO nodes ----------------
def _plan(state: CEOState) -> CEOState:
    _db.audit(state.get("task_id"), "ceo", "plan",
              f"planning the task: {state.get('task', '')[:120]}")
    return {"domain": route_task(state.get("task", ""))}


def _execute(state: CEOState) -> CEOState:
    domain = state["domain"]
    task_id = state.get("task_id")
    task = state.get("task", "")
    exec_id = _db.get_store().create_execution(task_id, domain) if task_id else None

    spec = DEPARTMENTS.get(domain)
    if not spec:
        if exec_id:
            _db.get_store().finish_execution(exec_id, "failed", "no department registered", 0)
        return {"error": f"no department registered named {domain}", "exec_id": exec_id}

    # Autonomy gate — block departments not allowed at this level
    from backend.app.services import store as _svc
    autonomy = int(_svc.get_setting("autonomy_level") or "1")
    if not _autonomy_allowed(autonomy, domain):
        if exec_id:
            _db.get_store().finish_execution(exec_id, "blocked",
                                             f"blocked by autonomy level {autonomy}", 0)
        return {"error": f"department '{domain}' blocked by autonomy level {autonomy}",
                "exec_id": exec_id}

    # publishing gate: no publishing execution before explicit human approval
    if spec.approval_policy == "human_required" and not state.get("human_confirmed"):
        if exec_id:
            _db.get_store().finish_execution(exec_id, "needs_approval",
                                             "awaiting founder sign-off", 0)
        return {"needs_approval": True, "exec_id": exec_id,
                "summary": "Publishing requires your sign-off — publish request queued"}

    kwargs: dict[str, Any] = {"task": task, "task_id": task_id}
    if spec.approval_policy == "human_required":
        kwargs["human_confirmed"] = bool(state.get("human_confirmed"))

    from agents import llm as _llm
    _llm.reset_usage_counter()
    try:
        out = spec.run(**kwargs)
    except Exception as e:  # noqa: BLE001
        out = {"ok": False, "error": str(e)}
    usage = _llm.usage_snapshot()
    # null, never 0, when the provider reported no usage metadata
    tokens_used = usage["total_tokens"] if usage and usage.get("source") == "measured" else None

    ok = bool(out.get("ok"))
    if exec_id:
        _db.get_store().finish_execution(
            exec_id,
            "success" if ok else "failed",
            str(out.get("summary") or out.get("error", ""))[:400],
            tokens_used)
    _db.audit(task_id, domain, "execute", str(out)[:600])
    return {"artifacts": out, "summary": out.get("summary") or "",
            "error": out.get("error") or "", "exec_id": exec_id}


def _evaluate(state: CEOState) -> CEOState:
    if state.get("needs_approval"):
        return {}
    if state.get("error"):
        return {"summary": f"Task failed: {state['error']}"}
    return {"summary": state.get("summary") or "Task executed"}


def _close(state: CEOState) -> CEOState:
    if state.get("task_id"):
        status = "failed" if state.get("error") else "success"
        _db.get_store().finish_task(state["task_id"], status, state.get("summary", ""))
    return {}


# ---------------- graph construction ----------------
_graph = None


def build_ceo_graph():
    g = StateGraph(CEOState)
    g.add_node("plan", _plan)
    g.add_node("execute", _execute)
    g.add_node("evaluate", _evaluate)
    g.add_node("close", _close)
    g.add_edge(START, "plan")
    g.add_edge("plan", "execute")
    g.add_edge("execute", "evaluate")
    g.add_edge("evaluate", "close")
    g.add_edge("close", END)
    return g.compile()


def get_ceo_graph():
    global _graph
    if _graph is None:
        _graph = build_ceo_graph()
    return _graph


def run_task(task: str, workspace: str = "default",
             human_confirmed: bool = False) -> dict[str, Any]:
    store = _db.get_store()
    task_id = store.create_task("run", "ceo", ref=task[:200],
                                input_text=task, )
    try:
        out = get_ceo_graph().invoke(
            {"task": task, "workspace": workspace, "task_id": task_id,
             "human_confirmed": bool(human_confirmed)},
            config={"recursion_limit": 8})
    except Exception as e:  # noqa: BLE001
        store.finish_task(task_id, "failed", str(e)[:400])
        return {"ok": False, "error": str(e), "task_id": task_id}

    artifacts = out.get("artifacts") or {}
    domain = out.get("domain") or route_task(task)
    ok = not bool(out.get("error")) and not bool(out.get("needs_approval"))
    return {"ok": ok,
            "task_id": task_id,
            "domain": domain,
            "summary": out.get("summary"),
            "artifacts": artifacts,
            "needs_approval": bool(out.get("needs_approval")),
            "llm_note": llm_last_note()}
