"""books.publishing — hard gate: no external publish without founder approval."""
from __future__ import annotations
import json
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from agents.common import HQState, ask_supervisor
from agents.capabilities.marketplace import etsy_create_draft, EtsyError
from backend.app import config as cfg
from backend.app.services import store as svc


def _etsy_publisher(state: HQState) -> HQState:
    progress = state.get("progress", [])
    slug = state.get("slug") or state.get("idea") or ""

    if not state.get("human_confirmed"):
        return {"error": "No human approval to publish",
                "progress": progress + ["FAILED publish"]}

    product = svc.get_product(slug)
    if not product:
        return {"error": f"Product ‘{slug}’ not found",
                "progress": progress + ["FAILED publish"]}
    if not product.get("pdf_path") or not Path(product["pdf_path"]).exists():
        return {"error": "No PDF ready — build the book first",
                "progress": progress + ["FAILED publish"]}

    story_file = cfg.BOOKS_DIR / slug / "story.json"
    try:
        story = json.loads(story_file.read_text(encoding="utf-8"))
        meta = {"title": story.get("etsy", {}).get("title", story.get("title", slug)),
                "description": story.get("etsy", {}).get("description", ""),
                "tags": (story.get("etsy") or {}).get("tags", []) or []}
        price = product.get("price_usd")
        if price is None:
            price = cfg.DEFAULT_BOOK_PRICE_USD
        outcome = etsy_create_draft(meta, product["pdf_path"],
                                    product.get("cover_path") or str(cfg.BOOKS_DIR / slug / "p0_cover.png"),
                                    price=price)
        svc.upsert_product(slug, product.get("title", slug),
                           status="draft_created",
                           pdf_path=product["pdf_path"],
                           cover_path=product.get("cover_path"),
                           final_file=product["pdf_path"])
        return {"summary": f"Etsy draft created — listing {outcome.get('listing_id')}",
                "artifacts": {"listing_id": outcome.get("listing_id"),
                              "shop_id": outcome.get("shop_id")},
                "progress": progress + [f"PUBLISH_DONE {slug}"]}
    except EtsyError as e:
        svc.upsert_product(slug, product.get("title", slug), status="draft_failed",
                           pdf_path=product.get("pdf_path"),
                           cover_path=product.get("cover_path"))
        return {"error": f"Etsy draft failed: {e}",
                "progress": progress + [f"FAILED publish {slug}"]}
    except Exception as e:  # noqa: BLE001
        svc.upsert_product(slug, product.get("title", slug), status="draft_failed",
                           pdf_path=product.get("pdf_path"),
                           cover_path=product.get("cover_path"))
        return {"error": f"Publishing failed: {e}",
                "progress": progress + [f"FAILED publish {slug}"]}


def _supervisor(state: HQState) -> HQState:
    nxt = ask_supervisor("books.publishing.supervisor",
                         ["etsy_publisher", "done"],
                         state.get("progress", []))
    return {"summary": nxt}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    return "etsy_publisher" if "etsy" in str(state.get("summary", "")).lower() else END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("etsy_publisher", _etsy_publisher)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"etsy_publisher": "etsy_publisher", END: END})
    g.add_edge("etsy_publisher", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default",
        slug: str | None = None, human_confirmed: bool = False) -> dict:
    slug = slug or task.strip().split()[-1]
    state: HQState = {"task": task, "slug": slug, "run_id": task_id,
                      "human_confirmed": bool(human_confirmed), "progress": []}
    try:
        result = _graph().invoke(state, config={"recursion_limit": 8})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    arts = result.get("artifacts") or {}
    return {"ok": True, "task_id": task_id, "summary": result.get("summary"), **arts}


from agents.registry import AgentSpec, DepartmentSpec, register

register(DepartmentSpec(
    key="books.publishing", sector="books",
    title_ar="Books — Publishing Supervisor", title_en="Books — Publishing Supervisor",
    description_ar="Uploads the book draft to Etsy after explicit human approval.",
    description_en='Etsy draft after your explicit approval (human-gated)',
    capabilities=["etsy_draft_listing"],
    allowed_tools=["etsy"],
    approval_policy="human_required",
    run=run, budget_limit_usd=20.0,
    agents=[
        AgentSpec("etsy_publisher", "creates the Etsy draft only after founder sign-off", "deterministic", ["marketplace_listings"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
