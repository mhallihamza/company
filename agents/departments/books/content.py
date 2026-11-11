"""books.content — Supervisor: idea → story → images → PDF (with fair review gate)."""
from __future__ import annotations
import json
import re
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState
from agents.capabilities import content as content_tools
from agents.capabilities import media, pdf
from agents.profiles import pick_profile
from agents.localization import get_language_profile, font_path_for
from backend.app.config import ARABIC_FONT, BOOKS_DIR
from backend.app.services import store as svc
import unicodedata


def _slugify(text: str) -> str:
    """ASCII-only slug — guarantees cross-platform safe filesystem paths."""
    # Keep ASCII alphanumerics + dashes/underscores; replace everything else
    keep = "".join(ch for ch in unicodedata.normalize("NFKD", text) if ch.isascii())
    keep = re.sub(r"[^a-z0-9_-]+", "_", keep.lower()).strip("_-")
    return (keep or "book")[:48] + "_" + str(abs(hash(text)) % 10**6)


def _story(state: HQState) -> HQState:
    idea = (state.get("idea") or state.get("task") or "an untitled children's story").strip()
    try:
        story = content_tools.write_story(idea, state.get("language", "en"), 12)
        slug = _slugify(story["title"])
        d = BOOKS_DIR / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        svc.upsert_product(slug, story["title"], status="story")
        return {"story": story, "slug": slug,
                "progress": state.get("progress", []) + [f"STORY_WRITER_DONE {slug}"],
                "summary": slug}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Story writing failed: {e}", "progress": state.get("progress", []) + ["FAILED story"]}


def _illustrator(state: HQState) -> HQState:
    progress = state.get("progress", [])
    slug = state.get("slug") or next((m.split(" ", 1)[1] for m in progress if m.startswith("STORY_WRITER_DONE ")), None)
    if not slug:
        return {"error": "No story ready for images", "progress": progress + ["FAILED images"]}
    try:
        d = BOOKS_DIR / slug
        story = json.loads((d / "story.json").read_text(encoding="utf-8"))
        paths = media.generate_images(story, d)
        svc.upsert_product(slug, story["title"], status="images", cover_path=paths[0] if paths else None)
        return {"slug": slug, "artifacts": {"images": paths},
                "progress": progress + [f"ILLUSTRATOR_DONE {slug}"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Image generation failed: {e}", "progress": progress + ["FAILED images"]}


def _pdf_builder(state: HQState) -> HQState:
    progress = state.get("progress", [])
    slug = state.get("slug") or next((m.split(" ", 1)[1] for m in progress if m.startswith("ILLUSTRATOR_DONE ")), None)
    if not slug:
        return {"error": "No images ready for layout", "progress": progress + ["FAILED pdf"]}
    try:
        d = BOOKS_DIR / slug
        story = json.loads((d / "story.json").read_text(encoding="utf-8"))
        imgs = [str(p) for p in sorted(d.glob("p*.png"),
                                       key=lambda p: p.stem)]
        out = d / "book.pdf"
        try:
            font_path = font_path_for(state.get("font_ref") or "font.dejavu")
        except FileNotFoundError:
            font_path = ARABIC_FONT  # documented fallback — the only font we ship
        pdf.build_book_pdf(story, imgs, out,
                           font_path=font_path,
                           language=str(state.get("language") or "en").lower(),
                           text_direction=str(state.get("text_direction") or "ltr"))
        # KDP interior (if marketplace is kdp)
        if (story.get("marketplace") or "kdp") in ("kdp", "both"):
            from agents.capabilities import kdp_interior
            kdp_out = d / "interior_kdp.pdf"
            kdp_interior.build_kdp_interior(story, imgs, kdp_out)
        svc.upsert_product(slug, story["title"], status="pdf", pdf_path=str(out),
                           cover_path=imgs[0] if imgs else None)
        return {"slug": slug, "pdf_path": str(out), "summary": f"Book built: {slug}",
                "artifacts": {"pdf_path": str(out)},
                "progress": progress + [f"PDF_BUILDER_DONE {slug}"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"PDF build failed: {e}", "progress": progress + ["FAILED pdf"]}


def _deterministic_next(options: list[str], progress: list[str]) -> str:
    """Sequential, language-agnostic next-step picker — deterministic, never uses the LLM."""
    done_tokens = {m.split(" ", 1)[0] for m in (progress or [])}
    for value in options:
        if value == "done":
            continue
        marker = value.upper().replace("-", "_").replace(" ", "_") + "_DONE"
        if marker not in done_tokens:
            return value
    return "done"


def _detect_product_type(task: str | None) -> str | None:
    if not task:
        return None
    t = task.lower()
    mapping = {
        "coloring": "coloring_book", "drawing": "drawing_workbook",
        "painting": "painting_workbook", "activity": "activity_workbook",
        "tracing": "tracing_workbook", "alphabet": "alphabet_workbook",
        "matching": "matching_activity", "maze": "maze_book",
        "bundle": "educational_bundle",
    }
    for kw, ptype in mapping.items():
        if kw in t:
            return ptype
    return None


def _product_brief(state: HQState) -> HQState:
    """Produce a Product Brief from a founder idea. Does NOT generate the book yet."""
    from agents.capabilities.product_brief import build_brief
    task = state.get("task") or state.get("idea") or ""
    ptype = state.get("product_type") or _detect_product_type(task)
    if not ptype:
        return {"error": "No product type detected. Say e.g. 'coloring book for new drawing themes' — or set state.product_type.",
                "progress": state.get("progress", []) + ["FAILED product_brief"]}
    marketplace = "kdp"
    if "etsy" in task.lower() or "printable" in task.lower():
        marketplace = "etsy"
    niche = {"kdp": "drawing", "etsy": "printables"}.get(marketplace, "drawing")
    brief = build_brief(
        {"title": task.split(":", 1)[-1].strip() or ptype.replace("_", " ").title(),
         "niche": niche, "age": "3-5",
         "differentiation": "Founder-selected opportunity from market research.",
         "seeds": []},
        marketplace, ptype)
    try:
        bid = svc.upsert_product_brief("brief_" + _slugify(brief["title"]), brief|{"status": "pending_approval"})
        return {"brief": brief, "brief_id": bid,
                "artifacts": {"brief": brief, "brief_id": bid},
                "summary": f"Brief ready for your approval: {brief['title']}",
                "progress": state.get("progress", []) + ["BRIEF_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Brief storage failed: {e}",
                "progress": state.get("progress", []) + ["FAILED product_brief"]}


def _run_and_finish(fn, state: HQState):
    out = fn(state)
    if not out.get("error"):
        out = dict(out)
        out["progress"] = out.get("progress", []) + ["PRODUCT_GENERATE_DONE"]
    return out


def _product_generate(state: HQState) -> HQState:
    """Generate the full product content from an approved brief."""
    from agents.capabilities.product_builder import build_product
    return _run_and_finish(_product_generate_impl, state)


def _product_generate_impl(state: HQState) -> HQState:
    from agents.capabilities.product_builder import build_product
    brief_rows = state.get("brief") or {}
    approved = False
    try:
        rows = svc.q("SELECT * FROM product_briefs WHERE status='approved' ORDER BY brief_id DESC LIMIT 1")
        if rows:
            brief_rows = json.loads(rows[0]["content"]) if isinstance(rows[0].get("content"), str) else rows[0]["content"]
            approved = True
    except Exception:  # noqa: BLE001
        pass
    if not approved:
        return {"error": "No approved Product Brief exists yet — approve a brief first, then re-run.",
                "progress": state.get("progress", []) + ["FAILED product_generate"]}
    try:
        story = build_product(brief_rows)
        slug = _slugify(story["title"])
        d = BOOKS_DIR / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        svc.upsert_product(slug, story["title"], status="story")
        return {"story": story, "slug": slug,
                "progress": state.get("progress", []) + [f"STORY_WRITER_DONE {slug}"],
                "summary": slug}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Product generation failed: {e}",
                "progress": state.get("progress", []) + ["FAILED product_generate"]}


def _supervisor(state: HQState) -> HQState:
    progress = state.get("progress", [])
    # stop after a brief is produced — founder approves, then regenerates with "generate"
    if not state.get("human_confirmed") and any(m.startswith("BRIEF_DONE") for m in progress):
        return {"summary": "done"}
    if any(m.startswith("PRODUCT_GENERATE_DONE") for m in progress):
        # content done — continue the deterministic pipeline: illustrator → pdf_builder
        if not any(m.startswith("ILLUSTRATOR_DONE") for m in progress):
            return {"summary": "illustrator"}
        if not any(m.startswith("PDF_BUILDER_DONE") for m in progress):
            return {"summary": "pdf_builder"}
        return {"summary": "done"}
    task = (state.get("task") or "").lower()
    if state.get("product_type") or _detect_product_type(task):
        if "brief" in task or "brief for" in task:
            nxt = "product_brief"
        elif "generate" in task or "create" in task:
            nxt = "product_generate"
        else:
            nxt = "product_brief"
        return {"summary": nxt}
    # Linear pipeline — shelf the LLM here. Deterministic else step is the same in every language.
    nxt = _deterministic_next(["story_writer", "illustrator", "pdf_builder", "done"], progress or [])
    return {"summary": nxt}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    if state.get("stop_after") == "story" and any(m.startswith("STORY_WRITER_DONE") for m in state.get("progress", [])):
        return END
    nxt = str(state.get("summary") or "").lower().strip()
    # supervisor returns the step name directly — use exact match first
    if nxt in ("story_writer", "illustrator", "pdf_builder",
               "product_brief", "product_generate"):
        return nxt
    # fallback: legacy substring match for older callers
    if "product_brief" in nxt:
        return "product_brief"
    if "product_generate" in nxt:
        return "product_generate"
    if "story" in nxt:
        return "story_writer"
    if "illustrat" in nxt or "image" in nxt:
        return "illustrator"
    if "pdf" in nxt:
        return "pdf_builder"
    return END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("product_brief", _product_brief)
    g.add_node("product_generate", _product_generate)
    g.add_node("story_writer", _story)
    g.add_node("illustrator", _illustrator)
    g.add_node("pdf_builder", _pdf_builder)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"product_brief": "product_brief",
                             "product_generate": "product_generate",
                             "story_writer": "story_writer", "illustrator": "illustrator",
                             "pdf_builder": "pdf_builder", END: END})
    g.add_edge("product_brief", "supervisor")
    g.add_edge("product_generate", "supervisor")
    g.add_edge("story_writer", "supervisor")
    g.add_edge("illustrator", "supervisor")
    g.add_edge("pdf_builder", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default",
        idea: str | None = None, stop_after: str = "",
        market: str | None = None, product_type: str | None = None) -> dict:
    try:
        profile = pick_profile(market)
        if profile is None:
            known = "us-en, fr-fr, sa-en" if not market else f"'{market}' not found or disabled"
            return {"ok": False, "task_id": task_id,
                    "error": f"no enabled market profile ({known}) — enable one at /profiles"}
        language = str(profile.get("language") or "en").lower()
        lang = get_language_profile(language)   # fail fast — unsupported code → UnsupportedLanguage
        state: HQState = {"task": idea or task or "a children's story", "idea": idea or task,
                          "run_id": task_id, "progress": [], "stop_after": stop_after or "",
                          "language": language,
                          "text_direction": lang.text_direction,
                          "font_ref": lang.font_ref,
                          "market": profile.get("label") or f"{profile.get('country')}-{language}".lower(),
                          "product_type": product_type or _detect_product_type(task or idea)}
        result = _graph().invoke(state, config={"recursion_limit": 12})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    arts = result.get("artifacts") or {}
    return {"ok": True, "task_id": task_id, "slug": result.get("slug"),
            "story": result.get("story"), "summary": result.get("summary"), **arts}


def build_existing(slug: str) -> dict:
    """Stage two: a saved, edited story → images → PDF."""
    state: HQState = {"task": slug, "idea": slug, "slug": slug, "run_id": None,
                      "progress": [f"STORY_WRITER_DONE {slug}"]}
    try:
        result = _graph().invoke(state, config={"recursion_limit": 12})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    if result.get("error"):
        return {"ok": False, "error": result["error"]}
    arts = result.get("artifacts") or {}
    return {"ok": True, "slug": slug, "summary": result.get("summary"), **arts}

from agents.registry import AgentSpec, DepartmentSpec, register

register(DepartmentSpec(
    key="books.content", sector="books",
    title_ar="Books — Content Supervisor", title_en="Books — Content Supervisor",
    description_ar="Writes the story, generates images, builds the 8.5x8.5 print PDF (Amiri).",
    description_en='Write → illustrate → print 8.5×8.5 book PDF with Arabic typography',
    capabilities=["write_story", "generate_images", "build_pdf"],
    allowed_tools=["llm", "image_renderer", "pdf_builder"],
    approval_policy="story_review",
    run=run, budget_limit_usd=20.0,
    agents=[
        AgentSpec("story_writer", "writes the children's story (JSON-validated)", "reasoning", ["content_generation"]),
        AgentSpec("illustrator", "renders character-consistent page images", "reasoning", ["image_generation"]),
        AgentSpec("pdf_builder", "composes the printable PDF (Amiri)", "deterministic", ["pdf_generation"]),
        AgentSpec("supervisor", "routes department worker order", "deterministic", []),
    ],
))
