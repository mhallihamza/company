"""finance — deterministic math (published KDP/Etsy numbers). The model never touches the numbers."""
from __future__ import annotations
import re
from datetime import date

from langgraph.graph import END, START, StateGraph

from agents.common import HQState, ask_supervisor
from agents.llm import get_chat_model
from agents.registry import AgentSpec, DepartmentSpec, register
from backend.app.config import REPORTS_DIR
from backend.app.services import store as svc

from agents.capabilities.finance import unit_economics  # noqa: F401 — single source of truth


def _calculator(state: HQState) -> HQState:
    task = (state.get("task") or "")
    try:
        m_price = re.search(r"(\d+(?:\.\d+)?)\s*(?:\$|usd|eur|price|dollar)", task, re.I)
        m_pages = re.search(r"(\d{1,4})\s*(?:pages|page|pp)", task, re.I)
        price = float(m_price.group(1)) if m_price else 4.99
        pages = int(m_pages.group(1)) if m_pages else 24
        result = unit_economics(price, pages)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"finance_{date.today().isoformat()}.md"
        etsy = result["etsy"]; kdp = result["kdp_paperback"]; ebook = result["kdp_ebook"]
        md = [
            f"### Unit Economics — {date.today().isoformat()}",
            f"_(source: {etsy.get('marketplace', 'US')}, rates last reviewed {etsy.get('last_reviewed', '—')})_",
            "",
            f"- Price: **{price} USD** · Pages: **{pages}**",
            "",
            "#### Etsy (digital download, US marketplace)",
            f"- Listing fee: {etsy['listing_fee']} USD",
            f"- Transaction (6.5%): {etsy['transaction_fee']} USD",
            f"- Payment processing (3.0% + $0.25): {etsy['payment_processing_fee']} USD",
            f"- Offsite ads: {etsy['offsite_ads_fee']} USD (off unless requested)",
            f"- **Total fees:** {etsy['total_fees']} USD",
            f"- **Net receipt:** {etsy['net_receipt']} USD",
            "",
            "#### KDP (paperback)",
            f"- Pages: {kdp['pages']}",
            f"- Royalty rate: {int(kdp['royalty_rate']*100)}%",
            f"- Printing cost (US B&W): {kdp['printing_cost']} USD",
            f"- **Royalty:** {kdp['royalty_usd']} USD",
            "",
            "#### KDP (eBook)",
            f"- Royalty 70%: {ebook['royalty_70_pct']} USD · Royalty 35%: {ebook['royalty_35_pct']} USD",
            "",
            "#### Assumptions",
            *[f"- {a}" for a in result["assumptions"]],
            "",
            f"_Sources: Etsy — {etsy.get('source_url')}_",
            f"_Source: KDP royalty — {kdp.get('source_url')}_",
        ]
        out.write_text("\n".join(md), encoding="utf-8")
        svc.add_report(str(out), "Unit Economics", out.read_text(encoding="utf-8"),
                       source="live" if (price and pages and price > 0) else "demo",
                       evidence={"price": price, "pages": pages})
        return {"summary": f"Finance analysis ready — {out.name}",
                "artifacts": {"finance": result, "report_path": str(out)},
                "progress": state.get("progress", []) + ["CALC_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Finance calculation failed: {e}", "progress": state.get("progress", []) + ["FAILED calculator"]}


def _supervisor(state: HQState) -> HQState:
    return {"summary": ask_supervisor("finance.supervisor",
                                      ["calculator", "done"],
                                      state.get("progress", []))}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    return "calculator" if "calculator" in str(state.get("summary", "")).lower() else END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("calculator", _calculator)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {"calculator": "calculator", END: END})
    g.add_edge("calculator", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default") -> dict:
    try:
        result = _graph().invoke({"task": task or "book 4.99 usd 24 pages",
                                  "run_id": task_id, "progress": []},
                                 config={"recursion_limit": 8})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    return {"ok": True, "task_id": task_id, "summary": result.get("summary"), **(result.get("artifacts") or {})}


register(DepartmentSpec(
    key="finance", sector="finance",
    title_ar="Finance & Margins", title_en="Finance",
    description_ar="Etsy/KDP fees + net margin per price × page count — deterministic Python.",
    description_en='Etsy/KDP fees + unit economics — Python math only',
    capabilities=["unit_economics", "fee_modeling"],
    allowed_tools=["unit_economics"],
    approval_policy="none",
    run=run, budget_limit_usd=5.0,
    agents=[
        AgentSpec("calculator", "pure-Python unit economics (Etsy/KDP fee model)", "deterministic", ["unit_economics"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
