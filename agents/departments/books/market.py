"""books.market — market supervisor: Trends + Etsy, then a report."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState, ask_supervisor, regex_json
from agents.llm import get_chat_model
from agents.registry import AgentSpec, DepartmentSpec, register
from agents.capabilities import research
from backend.app.config import REPORTS_DIR
from backend.app.services import store as svc

SEED_KEYWORDS = ["نشاط الحرفيين للأطفال".lower(), "activity book kids", "coloring book animals",
                 "arabic alphabet learning", "bilingual arabic book", "قصص قبل النوم"]


def _researcher(state: HQState) -> HQState:
    svc.audit(state.get("run_id"), "books.market", "scan_trends", "Trends+Etsy scan started")
    try:
        data = research.full_research(SEED_KEYWORDS)
        return {"research": data, "progress": state.get("progress", []) + ["RESEARCH_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Research failed: {e}", "progress": state.get("progress", []) + ["FAILED researcher"]}


def _reporter(state: HQState) -> HQState:
    try:
        research_data = state.get("research") or research.full_research(SEED_KEYWORDS)
        model = get_chat_model(temperature=0.2, max_tokens=1800)
        sys = ("[ROLE:report_writer]\nYou are a children's-book market analyst. Write IN ARABIC: "
               "pick top 3 niches, score each /10, propose one book idea each. Be honest about data limits.\n"
               f"RESEARCH_DATA: {json.dumps(research_data, ensure_ascii=False)[:2500]}\n")
        content = str(model.invoke([SystemMessage(content=sys), HumanMessage(content="اكتب التقرير")]).content)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"trends_{date.today().isoformat()}.md"
        out.write_text(content, encoding="utf-8")
        svc.add_report(str(out), "Market trends report", content)
        return {"summary": f"Market report ready: {out.name}",
                "artifacts": {"report_path": str(out)},
                "progress": state.get("progress", []) + ["REPORT_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Report writing failed: {e}", "progress": state.get("progress", []) + ["FAILED reporter"]}


def _supervisor(state: HQState) -> HQState:
    nxt = ask_supervisor("books.market.supervisor",
                         ["researcher", "reporter", "done"],
                         state.get("progress", []))
    return {"summary": nxt}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    nxt = str(state.get("summary") or "").lower()
    if "researcher" in nxt:
        return "researcher"
    if "reporter" in nxt:
        return "reporter"
    return END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("researcher", _researcher)
    g.add_node("reporter", _reporter)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"researcher": "researcher", "reporter": "reporter", END: END})
    g.add_edge("researcher", "supervisor")
    g.add_edge("reporter", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default") -> dict:
    try:
        result = _graph().invoke({"task": task or "تحليل السوق", "run_id": task_id, "progress": []},
                                 config={"recursion_limit": 12})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    arts = result.get("artifacts") or {}
    return {"ok": True, "task_id": task_id, "summary": result.get("summary"), **arts}


register(DepartmentSpec(
    key="books.market", sector="books",
    title_ar="الكتب — مشرف السوق", title_en="Books — Market Supervisor",
    description_ar="يمسح Trends ومنافسة Etsy ويصدر تقرير فرصة بالعربية",
    description_en='Google Trends + public Etsy scan → Arabic opportunity report',
    capabilities=["google_trends", "etsy_competition", "market_report"],
    allowed_tools=["web_research"],
    approval_policy="none",
    run=run, budget_limit_usd=10.0,
    agents=[
        AgentSpec("researcher", "scans Google Trends and public Etsy listings", "deterministic", ["web_research"]),
        AgentSpec("reporter", "writes the Arabic opportunity report", "reasoning", ["content_generation"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
