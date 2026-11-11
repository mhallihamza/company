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

SEED_KEYWORDS = ["drawing book kids", "coloring book kids",
                 "drawing and painting kids", "activity book preschool",
                 "tracing workbook kids", "painting book children"]


def _researcher(state: HQState) -> HQState:
    svc.audit(state.get("run_id"), "books.market", "research_scan",
              "KDP/Etsy/Trends market scan started")
    try:
        from agents.capabilities import market_research as mr
        task = state.get("task") or "scan"
        keywords = SEED_KEYWORDS + [task] if task and task != "scan" else SEED_KEYWORDS
        run_id = None
        try:
            run_id = svc.create_research_run(task, state.get("run_id"))
        except Exception:  # noqa: BLE001
            run_id = None

        envelopes = mr.collect_all(keywords)
        analysis = mr.analyze_records(envelopes)

        # persist raw observations + normalized records
        if run_id:
            svc.add_research_source(run_id, "composite_market_research", ", ".join(keywords),
                                    envelopes.get("etsy", {}).get("collected_at"),
                                    analysis["confidence"] == "high",
                                    "etsy" not in analysis["verified_sources"])
            for name, env in envelopes.items():
                for rec in env.get("records") or []:
                    try:
                        svc.add_competitor_observation(run_id, rec)
                    except Exception:  # noqa: BLE001 — best effort; never block the report
                        pass

        return {"research": {"envelopes": envelopes,
                              "normalized": analysis,
                              "competitors": analysis["competitor_examples"],
                              "confidence": analysis["confidence"]},
                "progress": state.get("progress", []) + ["RESEARCH_DONE"],
                "summary": "research done"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Research failed: {e}",
                "progress": state.get("progress", []) + ["FAILED researcher"]}


def _reporter(state: HQState) -> HQState:
    try:
        research_data = state.get("research") or {}
        collection = research_data if isinstance(research_data, dict) else {}
        envelopes = collection.get("envelopes", {})
        competitors = collection.get("competitors", [])
        confidence = collection.get("confidence", "low")

        verified = sorted({kw for kw in envelopes for kw, env in envelopes.items() if env.get("verified")})
        blind_spots = sorted({kw for kw, env in envelopes.items() if env.get("blind_spot") or not env.get("verified")})

        report_lines = [
            "# Children's Drawing & Painting Books — Market Research",
            "",
            f"**Confidence:** {confidence}  ",
            f"**Verified sources:** {', '.join(verified) if verified else 'none'}  ",
            f"**Blind-spot / unverified sources:** {', '.join(blind_spots) if blind_spots else 'none'}  ",
            "",
            "## Evidence gaps",
            "- Missing data is reported as missing — never invented.",
            "- Etsy/KDP competition numbers require live keys (ETSY_KEYSTRING + ETSY_SHARED_SECRET).",
            "- Google Trends averages are interest-over-time proxies, not sales volumes.",
            "",
            "## Competitor examples",
        ]
        for c in competitors:
            src = c.get("source", "?")
            report_lines.append(
                f"- **{c.get('title')}** — source: {src} — url: {c.get('url')} — price: ${c.get('price')} — rating: {c.get('rating')} — reviews: {c.get('reviews')}")

        model = get_chat_model(temperature=0.2, max_tokens=1800)
        prompt = (
            "[ROLE:report_writer]\nYou are a children's-book market analyst. Use ONLY the competitor "
            "records below. Write a concise English report recommending 5-10 product opportunities for "
            "kids aged 3-5 (drawing / painting / coloring / activity books). Do NOT fabricate numbers. "
            "Every recommendation must list evidence source links.\n"
            f"COLLECTED_RECORDS: {json.dumps(competitors, ensure_ascii=False)[:4000]}\n"
            f"CONFIDENCE: {confidence}\n")
        content = str(model.invoke([SystemMessage(content=prompt),
                                    HumanMessage(content="Write the market research report")]).content)

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"drawing_research_{date.today().isoformat()}.md"
        out.write_text(content, encoding="utf-8")
        svc.add_report(str(out), "Children's Drawing & Painting Books — Market Research", content)
        return {"summary": f"Market research ready: {out.name}",
                "artifacts": {"report_path": str(out), "body": content},
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
        result = _graph().invoke({"task": task or "market analysis", "run_id": task_id, "progress": []},
                                 config={"recursion_limit": 12})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    arts = result.get("artifacts") or {}
    return {"ok": True, "task_id": task_id, "summary": result.get("summary"), **arts}


register(DepartmentSpec(
    key="books.market", sector="books",
    title_ar="Books — Market Research", title_en="Books — Market Research",
    description_ar="Collects KDP/Etsy/Trends data with evidence, scores opportunities, emits a report.",
    description_en='Collects KDP/Etsy/Trends data with evidence, scores opportunities, emits a report.',
    capabilities=["google_trends", "etsy_competition", "market_report"],
    allowed_tools=["web_research"],
    approval_policy="none",
    run=run, budget_limit_usd=10.0,
    agents=[
        AgentSpec("researcher", "scans Google Trends and public Etsy listings", "deterministic", ["web_research"]),
        AgentSpec("reporter", "writes the research report with evidence", "reasoning", ["content_generation"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
