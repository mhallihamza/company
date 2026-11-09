"""intelligence — مسح سلة نيشات ثم تسجيل فرص مقيّمة وعدلها في قاعدة البيانات."""
from __future__ import annotations
import json
from datetime import date

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState, ask_supervisor, regex_json
from agents.llm import get_chat_model
from agents.registry import AgentSpec, DepartmentSpec, register
from agents.capabilities import research
from backend.app.config import REPORTS_DIR
from backend.app.services import store as svc

NICHES = ["activity book kids", "bilingual arabic kids", "educational workbook",
          "coloring book animals", "قصص قبل النوم", "arabic alphabet learning"]


def _scan(state: HQState) -> HQState:
    try:
        data = research.full_research(NICHES)
        return {"research": data, "progress": state.get("progress", []) + ["SCAN_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Scan failed: {e}", "progress": state.get("progress", []) + ["FAILED scan"]}


def _scorer(state: HQState) -> HQState:
    try:
        data = state.get("research") or research.full_research(NICHES)
        brief = (state.get("task") or "").strip()
        model = get_chat_model(temperature=0.2, max_tokens=1800)
        sys = ("[ROLE:intelligence.scorer]\nYou are a market-intelligence analyst. "
               "Return ONLY JSON {\"opportunities\": [{\"title\": str, \"niche\": str, "
               "\"score\": number, \"rationale\": str}], \"notes\": str}. "
               "Scores must be justified from the data, never invented sales.\n"
               f"BRIEF: {brief or 'general scan'}\n"
               f"RESEARCH_DATA: {json.dumps(data, ensure_ascii=False)[:3000]}\n")
        raw = str(model.invoke([SystemMessage(content=sys), HumanMessage(content="سجّل الفرص")]).content)
        parsed = regex_json(raw)
        opps = parsed.get("opportunities", [])[:10]
        lines = [f"### Market Intelligence Report — {date.today().isoformat()}", ""]
        if brief:
            lines += [f"**Brief:** {brief}", ""]
        for o in opps:
            oid = svc.add_opportunity("intelligence", str(o.get("title") or "فرصة")[:200],
                                      str(o.get("niche") or "general")[:80],
                                      float(o.get("score") or 0),
                                      {"rationale": o.get("rationale"), "notes": parsed.get("notes")})
            lines.append(f"- #{oid} ({o.get('score', 0)}/10) {o.get('title')}")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"intelligence_{date.today().isoformat()}.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        svc.add_report(str(out), "Market Intelligence Report", out.read_text(encoding="utf-8"))
        return {"summary": f"{len(opps)} opportunities logged — {out.name}",
                "artifacts": {"report_path": str(out)},
                "progress": state.get("progress", []) + ["SCORE_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Opportunity scoring failed: {e}", "progress": state.get("progress", []) + ["FAILED scorer"]}


def _supervisor(state: HQState) -> HQState:
    return {"summary": ask_supervisor("intelligence.supervisor",
                                      ["researcher", "scorer", "done"],
                                      state.get("progress", []))}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    nxt = str(state.get("summary", "")).lower()
    if "researcher" in nxt or "scan" in nxt:
        return "researcher"
    if "scorer" in nxt:
        return "scorer"
    return END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("researcher", _scan)
    g.add_node("scorer", _scorer)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"researcher": "researcher", "scorer": "scorer", END: END})
    g.add_edge("researcher", "supervisor")
    g.add_edge("scorer", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default") -> dict:
    try:
        result = _graph().invoke({"task": task or "مسح الفرص", "run_id": task_id, "progress": []},
                                 config={"recursion_limit": 12})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    return {"ok": True, "task_id": task_id, "summary": result.get("summary"), **(result.get("artifacts") or {})}


register(DepartmentSpec(
    key="intelligence", sector="intelligence",
    title_ar="ذكاء السوق", title_en="Market Intelligence",
    description_ar="مسح نيشات الكتب وتسجيل فرص مقيّمة قابلة للفرز في قاعدة البيانات",
    description_en='Scan niche baskets → scored, trackable opportunities in the DB',
    capabilities=["multi_niche_scan", "opportunity_scoring"],
    allowed_tools=["web_research"],
    approval_policy="none",
    run=run, budget_limit_usd=15.0,
    agents=[
        AgentSpec("researcher", "scans the niche basket (Trends + Etsy)", "deterministic", ["web_research"]),
        AgentSpec("scorer", "ranks opportunities with an LLM analyst + Python formulas", "reasoning", ["opportunity_scoring"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
