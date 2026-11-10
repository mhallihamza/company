"""product — turns an approved opportunity into a product candidate with an initial quality score."""
from __future__ import annotations
import json

from langgraph.graph import END, START, StateGraph

from agents.common import HQState, ask_supervisor
from agents.registry import AgentSpec, DepartmentSpec, register
from backend.app.services import store as svc

MIN_SCORE = 6.5


def _validator(state: HQState) -> HQState:
    task = (state.get("task") or "").strip()
    # the id can be «#42», «id:42», or id42
    import re
    m = re.search(r"\d{1,7}", task)
    oid = int(m.group(0)) if m else None
    if oid is None:
        rows = svc.list_opportunities(status="new", limit=1)
        if not rows:
            return {"error": "No new opportunity matches the brief",
                    "progress": state.get("progress", []) + ["FAILED validate"]}
        oid = rows[0]["opportunity_id"]
    rows = svc.q("SELECT * FROM opportunities WHERE opportunity_id=?", (oid,))
    if not rows:
        return {"error": f"No opportunity #{oid}", "progress": state.get("progress", []) + ["FAILED validate"]}
    opp = rows[0]
    if (opp.get("score") or 0) < MIN_SCORE:
        svc.set_opportunity_status(oid, "archived")
        return {"summary": f"Archived opportunity #{oid} — score {opp.get('score')} < {MIN_SCORE}",
                "artifacts": {"opportunity_id": oid, "decision": "archived"},
                "progress": state.get("progress", []) + ["VALIDATED archived"]}

    slug = f"opp_{oid}"
    title = opp.get("title", f"Opportunity #{oid}")
    svc.upsert_product(slug, title, status="candidate")
    svc.set_opportunity_status(oid, "pursuing")
    return {"summary": f"Candidate product «{title}» — hand off to the relevant department",
            "artifacts": {"opportunity_id": oid, "product_slug": slug},
            "progress": state.get("progress", []) + ["VALIDATED candidate"]}


def _supervisor(state: HQState) -> HQState:
    return {"summary": ask_supervisor("product.supervisor",
                                      ["validator", "done"],
                                      state.get("progress", []))}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    return "validator" if "validator" in str(state.get("summary", "")).lower() else END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("validator", _validator)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {"validator": "validator", END: END})
    g.add_edge("validator", "supervisor")
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
    key="product", sector="product",
    title_ar="Product Development", title_en="Product Development",
    description_ar="Turns approved opportunities into product candidates at minimum viable quality.",
    description_en='Opportunity → candidate product (deterministic go/no-go)',
    capabilities=["opportunity_validation", "product_candidate"],
    allowed_tools=["db"],
    approval_policy="none",
    run=run, budget_limit_usd=5.0,
    agents=[
        AgentSpec("validator", "scores opportunities against the go/no-go gate", "deterministic", []),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
