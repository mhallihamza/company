"""qa — deterministic gate before any publish/delivery: structure, images, PDF, Etsy limits, Arabic font."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from agents.common import HQState, ask_supervisor
from agents.registry import AgentSpec, DepartmentSpec, register
from backend.app.config import ARABIC_FONT, BOOKS_DIR
from backend.app.services import store as svc


from agents.capabilities.qa import check_product  # noqa: F401 — single source of truth


def _checker(state: HQState) -> HQState:
    slug = (state.get("task") or "").strip().split()[-1] if state.get("task") else ""
    if not slug or not (BOOKS_DIR / slug).exists():
        dirs = [p for p in BOOKS_DIR.iterdir() if p.is_dir()] if BOOKS_DIR.exists() else []
        dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        slug = dirs[0].name if dirs else ""
    if not slug:
        return {"error": "No books to check", "progress": state.get("progress", []) + ["FAILED qa"]}

    checks = check_product(slug)
    passed = sum(1 for _, ok, _ in checks if ok)
    verdict = "PASS ✅" if passed == len(checks) else "FAIL ❌"
    product = svc.get_product(slug)
    if verdict.startswith("PASS") and product:
        svc.upsert_product(slug, product["title"], status="qa")

    d = BOOKS_DIR / slug
    (d / "qa_latest.md").write_text(
        "\n".join([f"- {'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else "")
                   for name, ok, detail in checks]), encoding="utf-8")
    lines = [f"### QA Report — {slug} — {date.today().isoformat()}", "",
             f"**Verdict: {verdict}** ({passed}/{len(checks)})", ""]
    for name, ok, detail in checks:
        lines.append(f"- {'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""))
    content = "\n".join(lines)
    from backend.app.config import REPORTS_DIR
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"qa_{slug}_{date.today().isoformat()}.md"
    out.write_text(content, encoding="utf-8")
    svc.add_report(str(out), f"QA report {slug}", content)
    return {"summary": f"QA {verdict} — {passed}/{len(checks)} — {out.name}",
            "artifacts": {"qa_report": str(out), "verdict": verdict},
            "progress": state.get("progress", []) + ["CHECKS_DONE"]}


def _supervisor(state: HQState) -> HQState:
    return {"summary": ask_supervisor("qa.supervisor",
                                      ["checker", "done"],
                                      state.get("progress", []))}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    return "checker" if "checker" in str(state.get("summary", "")).lower() else END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("checker", _checker)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {"checker": "checker", END: END})
    g.add_edge("checker", "supervisor")
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
    key="qa", sector="qa",
    title_ar="الجودة والامتثال", title_en="QA & Compliance",
    description_ar="بوابة حتمية قبل النشر: بنية، صور، PDF، حدود Etsy، الخط العربي",
    description_en='Deterministic PASS/FAIL preflight gate before any publish',
    capabilities=["preflight_gate", "story_validation", "pdf_integrity", "etsy_limits"],
    allowed_tools=["qa_checks"],
    approval_policy="gate",
    run=run, budget_limit_usd=5.0,
    agents=[
        AgentSpec("checker", "preflight gate: structure, images, PDF, Etsy limits", "deterministic", ["qa_checks"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
