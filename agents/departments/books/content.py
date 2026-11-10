"""books.content — Supervisor: idea → story → images → PDF (with fair review gate)."""
from __future__ import annotations
import json
import re
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState, ask_supervisor
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
    idea = (state.get("idea") or state.get("task") or "قصة أطفال مجهولة").strip()
    try:
        story = content_tools.write_story(idea, state.get("language", "ar"), 12)
        slug = _slugify(story["title"])
        d = BOOKS_DIR / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        svc.upsert_product(slug, story["title"], status="story")
        return {"story": story, "slug": slug,
                "progress": state.get("progress", []) + [f"STORY_DONE {slug}"],
                "summary": slug}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Story writing failed: {e}", "progress": state.get("progress", []) + ["FAILED story"]}


def _illustrator(state: HQState) -> HQState:
    progress = state.get("progress", [])
    slug = state.get("slug") or next((m.split(" ", 1)[1] for m in progress if m.startswith("STORY_DONE ")), None)
    if not slug:
        return {"error": "No story ready for images", "progress": progress + ["FAILED images"]}
    try:
        d = BOOKS_DIR / slug
        story = json.loads((d / "story.json").read_text(encoding="utf-8"))
        paths = media.generate_images(story, d)
        svc.upsert_product(slug, story["title"], status="images", cover_path=paths[0] if paths else None)
        return {"slug": slug, "artifacts": {"images": paths},
                "progress": progress + [f"IMAGES_DONE {slug}"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Image generation failed: {e}", "progress": progress + ["FAILED images"]}


def _pdf_builder(state: HQState) -> HQState:
    progress = state.get("progress", [])
    slug = state.get("slug") or next((m.split(" ", 1)[1] for m in progress if m.startswith("IMAGES_DONE ")), None)
    if not slug:
        return {"error": "No images ready for layout", "progress": progress + ["FAILED pdf"]}
    try:
        d = BOOKS_DIR / slug
        story = json.loads((d / "story.json").read_text(encoding="utf-8"))
        imgs = [str(p) for p in sorted(d.glob("p*.png"),
                                       key=lambda p: p.stem)]
        out = d / "book.pdf"
        try:
            font_path = font_path_for(state.get("font_ref") or "font.amiri")
        except FileNotFoundError:
            font_path = ARABIC_FONT  # documented fallback — the only font we ship
        pdf.build_book_pdf(story, imgs, out,
                           font_path=font_path,
                           language=str(state.get("language") or "ar").lower(),
                           text_direction=str(state.get("text_direction") or "rtl"))
        svc.upsert_product(slug, story["title"], status="pdf", pdf_path=str(out),
                           cover_path=imgs[0] if imgs else None)
        return {"slug": slug, "pdf_path": str(out), "summary": f"Book built: {slug}",
                "artifacts": {"pdf_path": str(out)},
                "progress": progress + [f"PDF_DONE {slug}"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"PDF build failed: {e}", "progress": progress + ["FAILED pdf"]}


def _supervisor(state: HQState) -> HQState:
    nxt = ask_supervisor("books.content.supervisor",
                         ["story_writer", "illustrator", "pdf_builder", "done"],
                         state.get("progress", []))
    return {"summary": nxt}


def _route(state: HQState) -> str:
    if state.get("error"):
        return END
    if state.get("stop_after") == "story" and any(m.startswith("STORY_DONE") for m in state.get("progress", [])):
        return END
    nxt = str(state.get("summary") or "").lower()
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
    g.add_node("story_writer", _story)
    g.add_node("illustrator", _illustrator)
    g.add_node("pdf_builder", _pdf_builder)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"story_writer": "story_writer", "illustrator": "illustrator",
                             "pdf_builder": "pdf_builder", END: END})
    g.add_edge("story_writer", "supervisor")
    g.add_edge("illustrator", "supervisor")
    g.add_edge("pdf_builder", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default",
        idea: str | None = None, stop_after: str = "",
        market: str | None = None) -> dict:
    try:
        profile = pick_profile(market)
        if profile is None:
            known = "us-en, fr-fr, sa-ar" if not market else f"'{market}' not found or disabled"
            return {"ok": False, "task_id": task_id,
                    "error": f"no enabled market profile ({known}) — enable one at /profiles"}
        language = str(profile.get("language") or "ar").lower()
        lang = get_language_profile(language)   # fail fast — unsupported code → UnsupportedLanguage
        state: HQState = {"task": idea or task or "قصة أطفال", "idea": idea or task,
                          "run_id": task_id, "progress": [], "stop_after": stop_after or "",
                          "language": language,
                          "text_direction": lang.text_direction,
                          "font_ref": lang.font_ref,
                          "market": profile.get("label") or f"{profile.get('country')}-{language}".lower()}
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
                      "progress": [f"STORY_DONE {slug}"]}
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
    title_ar="الكتب — مشرف المحتوى", title_en="Books — Content Supervisor",
    description_ar="يكتب القصة ثم يولّد الصور ثم يبني PDF مربع 8.5×8.5 بخط Amiri",
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
