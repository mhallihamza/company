"""affiliate — discover public affiliate-program products + deterministic unit-economics math."""
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

from agents.capabilities.scoring import score_candidate  # noqa: F401 — single source of truth


def _scout(state: HQState) -> HQState:
    brief = (state.get("task") or "").strip()
    try:
        signals = research.google_trends([brief] if brief else ["kids activity books"])
        model = get_chat_model(temperature=0.5, max_tokens=1800)
        sys = ("[ROLE:affiliate.scout]\nFind PUBLIC affiliate-program products adjacent to children's books. "
               "Return ONLY JSON {\"candidates\": [{\"product\": str, \"est_price\": number, "
               "\"commission\": pct, \"cookie_days\": number, \"demand\": str, \"competition\": str, "
               "\"program_hint\": str}], \"sources\": str}. Never invent conversion or revenue numbers.\n"
               f"BRIEF: {brief or 'kids books, cards, stationery'}\n"
               f"TRENDS: {json.dumps(signals, ensure_ascii=False)[:700]}\n")
        parsed = regex_json(str(model.invoke([SystemMessage(content=sys),
                                              HumanMessage(content="candidates")]).content))
        candidates = parsed.get("candidates") or []
        if not candidates:
            raise ValueError("Analyst returned no valid list")
        return {"research": {"candidates": candidates, "sources": parsed.get("sources", "public")},
                "progress": state.get("progress", []) + ["RESEARCH_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Scout failed: {e}", "progress": state.get("progress", []) + ["FAILED scout"]}


def _analyst(state: HQState) -> HQState:
    try:
        raw = (state.get("research") or {}).get("candidates", [])
        brief = (state.get("task") or "affiliate")[:80]
        ranked = sorted((score_candidate(c) for c in raw),
                        key=lambda c: c["score"], reverse=True)
        lines = [f"### Affiliate Marketing Report — {date.today().isoformat()}",
                 "",
                 "Sources: public web + model knowledge + a deterministic formula. No private network data; figures are estimates.",
                 ""]
        for c in ranked[:10]:
            oid = svc.add_opportunity(
                "affiliate", f"{c.get('product')} — ({c.get('commission')}%)",
                brief, c["score"], {**c, "sources": (state.get("research") or {}).get("sources")})
            lines += [f"#### #{oid} — {c.get('product')}",
                      f"- Suggested program: {c.get('program_hint', 'search Amazon Associates / Awin / CJ / Impact')}",
                      f"- Unit commission: {c.get('unit_commission')} · score: **{c.get('score')}/10**",
                      f"- Cookie window: {c.get('cookie_days')} days" + (f" · risks: {', '.join(c['risks'])}" if c["risks"] else ""),
                      ""]
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"affiliate_{date.today().isoformat()}.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        svc.add_report(str(out), "Affiliate Marketing Report", out.read_text(encoding="utf-8"))
        return {"summary": f"{len(ranked)} candidates logged — {out.name}",
                "artifacts": {"report_path": str(out)},
                "progress": state.get("progress", []) + ["ANALYSIS_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Analyst failed: {e}", "progress": state.get("progress", []) + ["FAILED analyst"]}


def _supervisor(state: HQState) -> HQState:
    return {"summary": ask_supervisor("affiliate.supervisor",
                                      ["scout", "analyst", "done"],
                                      state.get("progress", []))}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    nxt = str(state.get("summary", "")).lower()
    if "scout" in nxt:
        return "scout"
    if "analyst" in nxt:
        return "analyst"
    return END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("scout", _scout)
    g.add_node("analyst", _analyst)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"scout": "scout", "analyst": "analyst", END: END})
    g.add_edge("scout", "supervisor")
    g.add_edge("analyst", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default") -> dict:
    try:
        result = _graph().invoke({"task": task or "affiliate products fit for kids books",
                                  "run_id": task_id, "progress": []},
                                 config={"recursion_limit": 12})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    return {"ok": True, "task_id": task_id, "summary": result.get("summary"), **(result.get("artifacts") or {})}


register(DepartmentSpec(
    key="affiliate", sector="affiliate",
    title_ar="Affiliate Marketing", title_en="Affiliate Marketing",
    description_ar="Discovers public affiliate products and ranks the strongest with deterministic math.",
    description_en='Find public affiliate programs → score economics + risks deterministically',
    capabilities=["candidate_discovery", "unit_economics_calc", "opportunity_scoring"],
    allowed_tools=["web_research"],
    approval_policy="content_gate",
    run=run, budget_limit_usd=10.0,
    agents=[
        AgentSpec("scout", "proposes public affiliate-program products", "reasoning", ["web_research"]),
        AgentSpec("analyst", "scores economics + risks deterministically", "deterministic", ["opportunity_scoring", "unit_economics"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
