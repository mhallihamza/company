"""marketing — truthful marketing pack (SEO/listing/Pinterest/calendar). Never publishes without approval."""
from __future__ import annotations
import json
import re
from datetime import date

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState, ask_supervisor, regex_json
from agents.llm import get_chat_model
from agents.registry import AgentSpec, DepartmentSpec, register
from backend.app.config import REPORTS_DIR
from backend.app.services import store as svc

REQUIRED = ("seo_keywords", "description", "pinterest", "calendar")


def _copywriter(state: HQState) -> HQState:
    brief = (state.get("task") or "").strip()
    if not brief:
        return {"error": "Brief is empty", "progress": state.get("progress", []) + ["FAILED copywriter"]}
    try:
        model = get_chat_model(temperature=0.6, max_tokens=1500)
        sys = ("[ROLE:marketing.copywriter]\nYou prepare a truthful go-to-market copy pack for an Arabic kids book. "
               "Return ONLY JSON {\"seo_keywords\": [str], \"description\": str, \"pinterest\": [str], "
               "\"calendar\": [str], \"disclaimer\": str}. No invented figures, no fake urgency.\n"
               f"BRIEF: {brief}\n")
        pack = regex_json(str(model.invoke([SystemMessage(content=sys),
                                            HumanMessage(content="جهّز الحزمة")]).content))
        missing = [k for k in REQUIRED if k not in pack]
        if missing:
            raise ValueError(f"الأقسام الناقصة: {missing}")
        pack["seo_keywords"] = [str(k)[:60] for k in pack["seo_keywords"]][:8]

        slug = re.sub(r"\W+", "_", brief, flags=re.UNICODE).strip("_")[:30] or "book"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"marketing_{slug}_{date.today().isoformat()}.md"
        lines = [f"### GTM Copy Pack — {brief}", "",
                 "#### SEO keywords", *[f"- {k}" for k in pack["seo_keywords"]],
                 "",
                 "#### Listing copy", pack["description"],
                 "",
                 "#### Pinterest ideas", *[f"- {p}" for p in pack["pinterest"]],
                 "",
                 "#### Promo calendar", *[f"- {c}" for c in pack["calendar"]],
                 "",
                 f"*{pack.get('disclaimer', 'اقتراح محتوى يحتاج موافقتك قبل النشر')}*"]
        out.write_text("\n".join(lines), encoding="utf-8")
        svc.add_report(str(out), f"GTM pack {brief[:40]}", out.read_text(encoding="utf-8"))
        return {"summary": f"Marketing pack ready — {out.name}",
                "artifacts": {"marketing_pack": str(out)},
                "progress": state.get("progress", []) + ["COPY_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Copywriter failed: {e}", "progress": state.get("progress", []) + ["FAILED copywriter"]}


def _supervisor(state: HQState) -> HQState:
    return {"summary": ask_supervisor("marketing.supervisor",
                                      ["copywriter", "done"],
                                      state.get("progress", []))}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    return "copywriter" if "copywriter" in str(state.get("summary", "")).lower() else END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("copywriter", _copywriter)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {"copywriter": "copywriter", END: END})
    g.add_edge("copywriter", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default") -> dict:
    try:
        result = _graph().invoke({"task": task, "run_id": task_id, "progress": []},
                                 config={"recursion_limit": 8})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    return {"ok": True, "task_id": task_id, "summary": result.get("summary"), **(result.get("artifacts") or {})}


register(DepartmentSpec(
    key="marketing", sector="marketing",
    title_ar="التسويق وSEO", title_en="Marketing & SEO",
    description_ar="يولّد كلمات SEO ووصف قوائم وأفكار Pinterest وتقويم ترويج — لا ينشر دون موافقتك",
    description_en='Truthful SEO + Pinterest + content calendar — never auto-publish',
    capabilities=["seo_keywords", "listing_copy", "pinterest_calendar"],
    allowed_tools=["content_generation"],
    approval_policy="content_gate",
    run=run, budget_limit_usd=10.0,
    agents=[
        AgentSpec("copywriter", "prepares the truthful SEO + Pinterest + calendar pack", "reasoning", ["content_generation"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
