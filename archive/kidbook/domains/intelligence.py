"""قسم ذكاء السوق — يبحث في نيشات الكتب ثم يسجّل فرصاً مُسجّلة في قاعدة البيانات.

الوكيل «scorer» لا يخترع أرقام بيع — يعلّق فقط على اتجاهات/منافسة فعلية من
Google Trends وEtsy + تحليل النموذج. كل فرصة تُحفظ بحالة 'new' لتُدار لاحقاً.
"""
from __future__ import annotations
import json
import re
from datetime import date

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage

from kidbook import config, tools
from kidbook.db import get_store
from kidbook.domains import DomainSpec, register_domain
from kidbook.domains.common import KidState, invoke_domain, ask_supervisor, log
from kidbook.llm import get_chat_model

NICHES = ["activity book kids", "bilingual arabic kids book", "educational workbook",
          "coloring book animals", "قصص قبل النوم", "arabic alphabet learning"]


def _researcher(state: KidState) -> KidState:
    store = get_store()
    log(store, state.get("run_id"), "مسح «Intelligence» لنيشات الكتب…")
    try:
        data = tools.full_research(NICHES)
        return {"research": data, "progress": state.get("progress", []) + ["SCAN_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل المسح: {e}", "progress": state.get("progress", []) + ["FAILED researcher"]}


def _scorer(state: KidState) -> KidState:
    store = get_store()
    log(store, state.get("run_id"), "تسجيل الفرص وفرزها…")
    try:
        research = state.get("research") or tools.full_research(NICHES)
        brief = (state.get("task") or "").strip()
        model = get_chat_model(temperature=0.2, max_tokens=2500)
        sys = ("[ROLE:intelligence.scorer]\nYou are a market intelligence analyst for a children's-book business. "
               "Given the research data and optional brief, return ONLY JSON: "
               '{"opportunities": [{"title": str, "niche": str, "score": number_0_to_10, "rationale": str}], "notes": str}.\n'
               "Base scores on the trends/competition attached. Never invent sales figures.\n"
               f"BRIEF: {brief or 'general opportunity scan'}\n"
               f"RESEARCH_DATA: {json.dumps(research, ensure_ascii=False)[:3500]}\n")
        raw = str(model.invoke([SystemMessage(content=sys),
                                HumanMessage(content="score opportunities")]).content)
        parsed = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        opps = parsed.get("opportunities", [])[:12]
        saved = []
        for o in opps:
            try:
                oid = store.add_opportunity(
                    "intelligence", str(o.get("title", "فرصة بلا عنوان"))[:200],
                    str(o.get("niche", "general"))[:80], float(o.get("score", 0)),
                    {"rationale": o.get("rationale"), "notes": parsed.get("notes"),
                     "sampled_at": research.get("sampled_at")})
                saved.append((oid, o.get("title"), o.get("score")))
            except Exception as e:  # noqa: BLE001
                log(store, state.get("run_id"), f"تعذر حفظ فرصة: {e}", "warn")

        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report = config.REPORTS_DIR / f"intelligence_{date.today()}.md"
        lines = [f"### تقرير ذكاء السوق — {date.today()}", ""]
        if brief:
            lines += [f"**التكليف:** {brief}", ""]
        for oid, title, score in saved:
            lines.append(f"- #{oid} **({score}/10)** {title}")
        lines += ["", f"**ملاحظات المحلل:** {parsed.get('notes', '—')}",
                  "", "تنبيه: الدرجات مبنية على إشارات الطلب/المنافسة الملتقطة فقط وليست ضماناً للربح."]
        report.write_text("\n".join(lines), encoding="utf-8")
        try:
            store.add_report(str(report), report.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return {"summary": f"{len(saved)} فرصة مسجلة في قاعدة البيانات — {report.name}",
                "artifacts": {**state.get("artifacts", {}), "report_path": str(report),
                              "opportunities": [s[0] for s in saved]},
                "progress": state.get("progress", []) + ["SCORE_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل التسجيل: {e}", "progress": state.get("progress", []) + ["FAILED scorer"]}


def _supervisor(state: KidState) -> KidState:
    nxt = ask_supervisor("intelligence.supervisor", state.get("progress", []),
                         [("researcher", "SCAN_DONE"), ("scorer", "SCORE_DONE"), ("done", None)])
    return {"summary": nxt}


def _route(state: KidState) -> str:
    if state.get("error"):
        return END
    return {"researcher": "researcher", "scorer": "scorer"}.get(
        (state.get("summary") or "").strip().lower(), END)


def build_graph():
    g = StateGraph(KidState)
    g.add_node("supervisor", _supervisor)
    g.add_node("researcher", _researcher)
    g.add_node("scorer", _scorer)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"researcher": "researcher", "scorer": "scorer", END: END})
    g.add_edge("researcher", "supervisor")
    g.add_edge("scorer", "supervisor")
    return g.compile()


def run(task, store, run_id=None):
    return invoke_domain(build_graph(),
                         {"task": task, "run_id": run_id, "progress": []},
                         store, run_id, "ذكاء السوق اكتمل")


register_domain(DomainSpec(
    key="intelligence",
    title="ذكاء السوق",
    description="يمسح Google Trends ومنافسة Etsy عبر سلة نيشات ثم يسجّل فرصاً قابلة للفرز في قاعدة البيانات",
    run=run,
    agents=["researcher (مسح Trends + Etsy)", "scorer (LLM: تسجيل الفرص 0-10)",
            "supervisor (researcher → scorer → done)"],
    capabilities=["multi_niche_scan", "opportunity_scoring", "opportunities_db"],
    keywords=["intelligence", "الفرص", "فرصة", "opportunity", "فرص جديدة", "أفكار أعمال"],
    approval_policy="none",
))
