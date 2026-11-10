"""intelligence — scan a niche basket, log scored opportunities with source + evidence."""
from __future__ import annotations
import json
import os
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
          "coloring book animals", "bedtime stories", "arabic alphabet learning"]


def _allow_demo() -> bool:
    return os.getenv("AIHQ_ALLOW_DEMO", "").lower() in ("1", "true", "yes")


def _is_demo_sourced(data: dict) -> bool:
    """Return True if every trend/competition entry carries source=demo."""
    details: list[str] = []
    for v in ((data.get("google_trends") or {}).get("keywords") or {}).values():
        if isinstance(v, dict):
            details.append(str(v.get("source", "demo")))
    for v in (data.get("etsy_competition") or {}).values():
        if isinstance(v, dict):
            details.append(str(v.get("source", "demo")))
    return bool(details) and all(d == "demo" for d in details)


def _scan(state: HQState) -> HQState:
    try:
        data = research.full_research(NICHES)
        return {"research": data, "progress": state.get("progress", []) + ["SCAN_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Scan failed: {e}",
                "progress": state.get("progress", []) + ["FAILED scan"]}


def _scorer(state: HQState) -> HQState:
    try:
        data = state.get("research") or research.full_research(NICHES)
        brief = (state.get("task") or "").strip()

        if _is_demo_sourced(data) and not _allow_demo():
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            out = REPORTS_DIR / f"intelligence_{date.today().isoformat()}.md"
            out.write_text(
                f"### Market Intelligence — {date.today().isoformat()}\n\n"
                f"**Brief:** {brief or 'general scan'}\n\n"
                f"**Results:** DEMO data unavailable (no live keys).\n"
                f"Set `AIHQ_ALLOW_DEMO=1` to allow clearly-labelled demo scoring.\n",
                encoding="utf-8")
            svc.add_report(str(out), "Market Intelligence — demo blocked",
                           out.read_text(encoding="utf-8"),
                           source="demo", evidence={"reason": "AIHQ_ALLOW_DEMO=0"})
            return {"summary": "Live data unavailable — demo gate blocked scoring (set AIHQ_ALLOW_DEMO=1 to allow)",
                    "artifacts": {"report_path": str(out)},
                    "progress": state.get("progress", []) + ["SCORE_DONE"]}

        model = get_chat_model(temperature=0.2, max_tokens=1800)
        sys = ("[ROLE:intelligence.scorer]\nYou are a market-intelligence analyst. "
               "Return ONLY JSON {\"opportunities\": [{\"title\": str, \"niche\": str, "
               "\"score\": number, \"rationale\": str}], \"notes\": str}. "
               "Scores MUST be justified from the data you received. If the data is demo/partial, "
               "say so explicitly. Never invent sales numbers.\n"
               f"BRIEF: {brief or 'general scan'}\n"
               f"RESEARCH_DATA: {json.dumps(data, ensure_ascii=False)[:3000]}\n")
        raw = str(model.invoke([SystemMessage(content=sys),
                                HumanMessage(content="score opportunities")]).content)
        parsed = regex_json(raw)
        opps = (parsed.get("opportunities") or [])[:10]
        is_demo = _is_demo_sourced(data)
        src = "demo" if is_demo else "partial"

        lines = [f"### Market Intelligence Report — {date.today().isoformat()}  _(source: {src})_",
                 ""]
        if brief:
            lines += [f"**Brief:** {brief}", ""]
        for o in opps:
            title = str(o.get("title") or "untitled opportunity")[:200]
            niche = str(o.get("niche") or "general")[:80]
            score = svc.clamp_score(o.get("score"))
            oid = svc.add_opportunity("intelligence", title, niche, score,
                                      {"rationale": o.get("rationale"),
                                       "notes": parsed.get("notes")},
                                      source=src,
                                      evidence={"research": data, "demo": is_demo})
            lines.append(f"- #{oid} ({score}/10) [{src.upper()}] {title}")

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"intelligence_{date.today().isoformat()}.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        svc.add_report(str(out), "Market Intelligence Report",
                       out.read_text(encoding="utf-8"),
                       source=src, evidence={"demo": is_demo})
        return {"summary": f"{len(opps)} opportunities (source={src}) logged — {out.name}",
                "artifacts": {"report_path": str(out)},
                "progress": state.get("progress", []) + ["SCORE_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Opportunity scoring failed: {e}",
                "progress": state.get("progress", []) + ["FAILED scorer"]}


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
        result = _graph().invoke({"task": task or "opportunity scan",
                                  "run_id": task_id, "progress": []},
                                 config={"recursion_limit": 12})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    return {"ok": True, "task_id": task_id,
            "summary": result.get("summary"),
            **(result.get("artifacts") or {})}


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
        AgentSpec("researcher", "scans niche basket (Trends + Etsy, live/partial when keys exist; blocked otherwise)", "deterministic", ["web_research"]),
        AgentSpec("scorer",     "LLM analyst ranking the captured evidence — scores clamped 0-10 in code; demo-tagged when unverified", "reasoning", []),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
