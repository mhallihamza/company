"""قسم التسويق — محتوى SEO وقنوات وترويج؛ لا ينشر شيئاً بنفسه.

أي محتوى يُقترح يتطلب موافقتك قبل التسليم/النشر. الأرقام في الاقتراحات
تكون نوعية فقط ما لم تُغذَّه ببيانات حقيقية من متجرك.
"""
from __future__ import annotations
import json
import re
from datetime import date

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage

from kidbook import config
from kidbook.db import get_store
from kidbook.domains import DomainSpec, register_domain
from kidbook.domains.common import KidState, invoke_domain, ask_supervisor, log
from kidbook.llm import get_chat_model

REQUIRED = ("seo_keywords", "description", "pinterest", "calendar")


def _copywriter(state: KidState) -> KidState:
    store = get_store()
    brief = (state.get("task") or "").strip()
    log(store, state.get("run_id"), f"«Copywriter» يجهز حزمة تسويق — {brief[:80]}")
    try:
        model = get_chat_model(temperature=0.6, max_tokens=1800)
        sys = ("[ROLE:marketing.copywriter]\nYou prepare an honest go-to-market copy pack for a children's book. "
               "Return ONLY JSON: {\"seo_keywords\": [str<=8], \"description\": str, "
               "\"pinterest\": [str<=4 ideas], \"calendar\": [str 3-7 day ideas], \"disclaimer\": str}.\n"
               "No invented sales numbers, no fake urgency, keep claims product-true.\n"
               f"BRIEF: {brief}\n")
        raw = str(model.invoke([SystemMessage(content=sys),
                                HumanMessage(content="create the copy pack")]).content)
        pack = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        missing = [k for k in REQUIRED if k not in pack]
        if missing:
            raise ValueError(f"النموذج لم يُرجع الأقسام: {missing}")
        pack["seo_keywords"] = [str(k)[:60] for k in pack["seo_keywords"]][:8]

        slug = re.sub(r"\W+", "_", brief, flags=re.UNICODE).strip("_")[:30] or "book"
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = config.REPORTS_DIR / f"marketing_{slug}_{date.today()}.md"
        lines = [f"### حزمة تسويق — {brief}",
                 "",
                 "#### كلمات SEO", *[f"- {k}" for k in pack["seo_keywords"]],
                 "",
                 "#### وصف القائمة (Etsy/KDP)", pack["description"],
                 "",
                 "#### أفكار Pinterest/بوسترات", *[f"- {p}" for p in pack["pinterest"]],
                 "",
                 "#### تقويم ترويجي مبدئي", *[f"- {c}" for c in pack["calendar"]],
                 "",
                 f"*تنبيه: {pack.get('disclaimer', 'اقتراح محتوى يحتاج موافقتك قبل النشر.')}*"]
        out.write_text("\n".join(lines), encoding="utf-8")
        try:
            store.add_report(str(out), out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return {"summary": f"حزمة التسويق جاهزة — {out.name}",
                "artifacts": {**state.get("artifacts", {}), "marketing_pack": str(out)},
                "progress": state.get("progress", []) + ["COPY_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل «Copywriter»: {e}", "progress": state.get("progress", []) + ["FAILED copywriter"]}


def _supervisor(state: KidState) -> KidState:
    nxt = ask_supervisor("marketing.supervisor", state.get("progress", []),
                         [("copywriter", "COPY_DONE"), ("done", None)])
    return {"summary": nxt}


def _route(state: KidState) -> str:
    if state.get("error"):
        return END
    return "copywriter" if (state.get("summary") or "").strip().lower() == "copywriter" else END


def build_graph():
    g = StateGraph(KidState)
    g.add_node("supervisor", _supervisor)
    g.add_node("copywriter", _copywriter)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {"copywriter": "copywriter", END: END})
    g.add_edge("copywriter", "supervisor")
    return g.compile()


def run(task, store, run_id=None):
    return invoke_domain(build_graph(),
                         {"task": task, "run_id": run_id, "progress": []},
                         store, run_id, "حزمة التسويق جاهزة")


register_domain(DomainSpec(
    key="marketing",
    title="التسويق وSEO",
    description="يولّد كلمات SEO ووصف قوائم وأفكار Pinterest وتقويم ترويجي — لا ينشر دون موافقتك",
    run=run,
    agents=["copywriter (LLM: حزمة تسويق JSON محققة)",
            "supervisor (copywriter → done)"],
    capabilities=["seo_keywords", "listing_copy", "pinterest_calendar"],
    keywords=["marketing", "تسويق", "seo", "pinterest", "كلمات مفتاحية", "وصف المنتج"],
    approval_policy="content_gate",
))
