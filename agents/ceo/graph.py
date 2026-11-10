"""CEO graph — القائد المركزي: plan → execute exchange → evaluate → close.

ينفذ التوجيه الأصلي (Deterministic Routing) + يرتد إلى النموذج عند عدم الكفاية:
  plan → route (keyword/LLM من السجل) → execute (قسم) → evaluate (الحكم) → close
هذا التدفق هوالوثني (LangGraph) وليس سلسلة استدعاءات برمجية، كي يمكن لاحقاً
إضافة Kill Switches/Human Loops لكل عقدة على حدة.
"""
from __future__ import annotations
import json
import re
from typing import Any

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState  # noqa: F401 — تُحتفظ للوراثة المستقبلية
from agents.ceo.state import CEOState
from agents.llm import get_chat_model, llm_last_note
from agents.registry import DEPARTMENTS, list_departments
from backend.app import db as _db
from backend.app.services import store as svc


_WORD = re.compile(r"\b[\w\u0600-\u06FF]+\b", re.UNICODE)


def _keyword_pick(text: str) -> str | None:
    rules = [
        ("affiliate", ("affiliate", "عمولة", "بالعمولة", "لعمولة", "commission")),
        ("qa",         ("qa", "quality", "inspection", "جودة", "فحص", "امتثال", "preflight")),
        ("finance",    ("finance", "رسوم", "هامش", "ربح", "ربحية", "عائد", "تكلفة",
                        "margin", "profit", "usd", "price", "pricing", "سعر")),
        ("marketing",  ("marketing", "seo", "pinterest", "تسويق")),
        ("intelligence", ("intelligence", "فرص", "فرصة", "opportunity")),
        ("books.market", ("trend", "market", "منافس", "السوق", "سوق")),
        ("books.publishing", ("publish", "etsy", "kdp", "etsy", "انشر", "نشر")),
        ("books.content", ("story", "content", "قصة", "حكاية", "اكتب", "ألف")),
        ("product",     ("product", "candidate", "مرشح")),
    ]
    words = _WORD.findall(text.lower())
    word_set = set(words)
    # max keyword length wins; tie-breaker = domain specificity (affiliate > qa > finance > …)
    best: tuple[int, int, str] | None = None
    for rank, (domain, keys) in enumerate(rules):
        hits = [k.lower() for k in keys if k.lower() in word_set]
        if hits:
            key_len = max(len(h) for h in hits)
            candidate = (key_len, -rank, domain)
            if best is None or candidate > best:
                best = candidate
    return best[2] if best else None


def route_task(task: str) -> str:
    ids = list_departments()
    try:
        model = get_chat_model(temperature=0, max_tokens=80)
        sys = ("[ROLE:orchestrator]\nYou are the CEO router. Departments:\n"
               + "\n".join(f"- {d.key} — {d.description_ar}" for d in ids)
               + '\nReply ONLY JSON {"domain": "<key>"}')
        raw = model.invoke([SystemMessage(content=sys),
                            HumanMessage(content=task)]).content
        picked = json.loads(re.search(r"\{.*?\}", str(raw), re.S).group(0))["domain"]
        return picked if picked in DEPARTMENTS else _keyword_pick(task) or "books.content"
    except Exception:  # noqa: BLE001
        return _keyword_pick(task) or "books.content"


# ---------------- عقد الـ CEO ----------------
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

    # بوابة النشر: لا تنفيذ نشر قبل موافقة بشرية صريحة
    if spec.approval_policy == "human_required" and not state.get("human_confirmed"):
        if exec_id:
            _db.get_store().finish_execution(exec_id, "needs_approval",
                                             "awaiting founder sign-off", 0)
        return {"needs_approval": True, "exec_id": exec_id,
                "summary": "Publishing requires your sign-off — publish request queued"}

    kwargs: dict[str, Any] = {"task": task, "task_id": task_id}
    if spec.approval_policy == "human_required":
        kwargs["human_confirmed"] = bool(state.get("human_confirmed"))

    try:
        out = spec.run(**kwargs)
    except Exception as e:  # noqa: BLE001
        out = {"ok": False, "error": str(e)}

    ok = bool(out.get("ok"))
    if exec_id:
        _db.get_store().finish_execution(
            exec_id,
            "success" if ok else "failed",
            str(out.get("summary") or out.get("error", ""))[:400],
            int(out.get("tokens_used", 0) or 0))
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


# ---------------- بناء الرسم ----------------
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
