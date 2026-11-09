"""قسم التسويق بالعمولة — يكتشف منتجات لها برامج عمولة عامة ويقيّمها.

المنهج صريح: لا توجد مفاتيح شبكات تابعة هنا؛ المصادر = ويب عام (Trends +
ملاحظة Etsy/Amazon) + معرفة النموذج + حساب حتمي للوحدة الاقتصادية.
كل الأرقام "تقديرات مبدئية" وليست وعوداً بالأرباح.
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

# ---- حساب حتمي: لا يعتمد على النموذج في الأرقام ----
DEMAND_SCORE = {"high": 8.0, "rising": 8.0, "steady": 6.0, "low": 3.0, "unknown": 5.0}
COMPETITION_SCORE = {"low": 9.0, "medium": 5.0, "high": 3.0, "unknown": 5.0}


def score_candidate(c: dict) -> dict:
    price = float(c.get("est_price") or 0)
    pct = float(c.get("commission") or 0)
    cookie = float(c.get("cookie_days") or 14)
    demand = str(c.get("demand", "unknown")).lower()
    comp = str(c.get("competition", "unknown")).lower()
    unit = round(price * pct / 100.0, 2)
    risk = []
    if comp == "high":
        risk.append("منافسة عالية")
    if cookie <= 7:
        risk.append("نافذة روابط قصيرة")
    if demand in ("low", "unknown"):
        risk.append("طلب ضعيف/غير مؤكد")
    score = (DEMAND_SCORE.get(demand, 5.0) * 0.35
             + COMPETITION_SCORE.get(comp, 5.0) * 0.25
             + min(pct / 15.0, 1.0) * 10 * 0.25
             + min(cookie / 30.0, 1.0) * 10 * 0.15)
    return {**c, "unit_commission": unit, "score": round(score, 1), "risks": risk}


def _scout(state: KidState) -> KidState:
    store = get_store()
    brief = (state.get("task") or "").strip()
    log(store, state.get("run_id"), f"«Scout» يبحث عن منتجات عمولة — {brief[:80] or 'عام'}")
    try:
        # إشارة السوق العامة تثري معرفة النموذج (دون أرقام مختلقة)
        signals = tools.google_trends([brief] if brief else ["kids activity books"])
        model = get_chat_model(temperature=0.5, max_tokens=2200)
        sys = ("[ROLE:affiliate.scout]\nYou help a small publisher find PUBLIC affiliate-program products "
               "to promote (books/workbooks/edu items). Return ONLY JSON:\n"
               '{"candidates": [{"product": str, "est_price": number, "commission": pct_number, '
               '"cookie_days": number, "demand": "high|steady|rising|low|unknown", '
               '"competition": "low|medium|high|unknown", "program_hint": str}], "sources": str}\n'
               "Do NOT invent conversion rates or revenues. Prefer items adjacent to children's books.\n"
               f"BRIEF: {brief or 'children book & edutainment items'}\n"
               f"TRENDS_SIGNAL: {json.dumps(signals, ensure_ascii=False)[:800]}\n")
        raw = str(model.invoke([SystemMessage(content=sys),
                                HumanMessage(content="list candidates")]).content)
        parsed = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        candidates = parsed.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("المحلل لم يُرجع قائمة منتجات صالحة")
        return {"research": {"candidates": candidates, "sources": parsed.get("sources", "public")},
                "progress": state.get("progress", []) + ["RESEARCH_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل «Scout»: {e}", "progress": state.get("progress", []) + ["FAILED scout"]}


def _analyst(state: KidState) -> KidState:
    store = get_store()
    log(store, state.get("run_id"), "حساب الوحدة الاقتصادية وفرز الفرص…")
    try:
        raw_cands = (state.get("research") or {}).get("candidates", [])
        enriched = sorted((score_candidate(c) for c in raw_cands),
                          key=lambda c: c["score"], reverse=True)
        saved = []
        for c in enriched[:10]:
            oid = store.add_opportunity(
                "affiliate", f"{c.get('product')} (عمولة {c.get('commission')}%)",
                brief_niche(state), c["score"],
                {**c, "sources": (state.get("research") or {}).get("sources")})
            saved.append((oid, c))

        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report = config.REPORTS_DIR / f"affiliate_{date.today()}.md"
        lines = [f"### تقرير التسويق بالعمولة — {date.today()}",
                 "",
                 "**المصادر:** ويب عام + معرفة النموذج + معادلة ترجيح حتمية. "
                 "لا توجد بيانات شبكات تابعة خاصة؛ كل رقم هنا تقديري.",
                 ""]
        for oid, c in saved:
            lines += [f"#### #{oid} — {c.get('product')}",
                      f"- برنامج مقترح: {c.get('program_hint', 'ابحث في Amazon Associates / Awin / CJ / Impact')}",
                      f"- السعر التقريبي: {c.get('est_price')} · عمولة: {c.get('commission')}% "
                      f"· على كل وحدة: {c.get('unit_commission')}",
                      f"- نافذة الرابط: {c.get('cookie_days')} يوم · الطلب: {c.get('demand')} · المنافسة: {c.get('competition')}",
                      f"- **الدرجة: {c.get('score')}/10**" + (f" · مخاطر: {', '.join(c['risks'])}" if c.get('risks') else ""),
                      ""]
        if saved:
            lines += ["> **الخطوة التالية:** تحقق من أهلية حسابك في الشبكة، واختر #id واحدًا لتجريبه، "
                      "ثم اطلب من قسم التسويق محتوى SEO للحملة — لا تنشر قبل موافقتك."]
        report.write_text("\n".join(lines), encoding="utf-8")
        try:
            store.add_report(str(report), report.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return {"summary": f"{len(saved)} منتج مرشح مسجل — {report.name}",
                "artifacts": {**state.get("artifacts", {}), "report_path": str(report),
                              "opportunities": [s[0] for s in saved]},
                "progress": state.get("progress", []) + ["ANALYSIS_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل «Analyst»: {e}", "progress": state.get("progress", []) + ["FAILED analyst"]}


def brief_niche(state: KidState) -> str:
    return (state.get("task") or "affiliate")[:80]


def _supervisor(state: KidState) -> KidState:
    nxt = ask_supervisor("affiliate.supervisor", state.get("progress", []),
                         [("researcher", "RESEARCH_DONE"), ("analyst", "ANALYSIS_DONE"), ("done", None)])
    return {"summary": nxt}


def _route(state: KidState) -> str:
    if state.get("error"):
        return END
    return {"researcher": "researcher", "analyst": "analyst"}.get(
        (state.get("summary") or "").strip().lower(), END)


def build_graph():
    g = StateGraph(KidState)
    g.add_node("supervisor", _supervisor)
    g.add_node("researcher", _scout)   # عقدة الوكيل «scout»
    g.add_node("analyst", _analyst)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"researcher": "researcher", "analyst": "analyst", END: END})
    g.add_edge("researcher", "supervisor")
    g.add_edge("analyst", "supervisor")
    return g.compile()


def run(task, store, run_id=None):
    return invoke_domain(build_graph(),
                         {"task": task, "run_id": run_id, "progress": []},
                         store, run_id, "بحث التسويق بالعمولة اكتمل")


register_domain(DomainSpec(
    key="affiliate",
    title="التسويق بالعمولة",
    description="يكتشف منتجات برامج عمولة عامة، يحسب الوحدة الاقتصادية بمعادلة حتمية، ويسجّل الأقوى كفرص",
    run=run,
    agents=["scout (LLM: ترشيح منتجات + نبض Trends)",
            "analyst (حسابي حتمي: عمولات ومخاطر ودرجة 0-10)",
            "supervisor (scout → analyst → done)"],
    capabilities=["candidate_discovery", "unit_economics_calc", "opportunity_scoring"],
    keywords=["affiliate", "عمولة", "تابع", "commission", "associate", "ترويج منتج"],
    approval_policy="content_gate",
))
