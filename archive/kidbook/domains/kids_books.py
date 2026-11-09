"""قطاع «كتب الأطفال» — ثلاث مشرفين ولكل منهم وكلاء متخصصون.

    kids_books.market      مشرف السوق: بحث Google Trends ومنافسة Etsy → تقرير فرصة
    kids_books.content     مشرف المحتوى: قصة → صور → PDF مع بوابة مراجعة بشرية
    kids_books.publishing  مشرف النشر: تأكيد بشري ← رفع مسودة Etsy فقط
"""
from __future__ import annotations
import json
import re
from datetime import date
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage

from kidbook import config, tools
from kidbook.domains import DomainSpec, register_domain
from kidbook.llm import get_chat_model
from kidbook.db import get_store
from kidbook.domains.common import (
    KidState, DomainError, slugify, invoke_domain, ask_supervisor, log,
)


# ======================================================================
# مشرف السوق
# ======================================================================
def _market_researcher(state: KidState) -> KidState:
    store = get_store()
    log(store, state.get("run_id"), "بحث Google Trends وEtsy…")
    try:
        data = tools.full_research(config.SEED_KEYWORDS)
        return {"research": data, "progress": state.get("progress", []) + ["RESEARCH_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل بحث السوق: {e}", "progress": state.get("progress", []) + ["FAILED researcher"]}


def _market_reporter(state: KidState) -> KidState:
    store = get_store()
    log(store, state.get("run_id"), "المحلل يكتب تقرير الفرصة…")
    try:
        research = state.get("research") or tools.full_research(config.SEED_KEYWORDS)
        model = get_chat_model(temperature=0.2, max_tokens=2500)
        sys = ("[ROLE:report_writer]\nYou are a children's-book market analyst. "
               "Write the report IN ARABIC: rank niches by opportunity (rising demand, low competition), "
               "score each /10, propose 3 concrete book ideas for the best niche (title, age, hook). "
               "Be honest about data limits.\n"
               f"RESEARCH_DATA: {json.dumps(research, ensure_ascii=False)[:4000]}\n")
        content = str(model.invoke([SystemMessage(content=sys),
                                    HumanMessage(content="اكتب التقرير")]).content)
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = config.REPORTS_DIR / f"trends_{date.today()}.md"
        path.write_text(content, encoding="utf-8")
        try:
            store.add_report(str(path), content)
        except Exception as e:  # noqa: BLE001
            log(store, state.get("run_id"), f"تعذر تسجيل التقرير في قاعدة البيانات: {e}", "warn")
        return {"summary": f"تقرير السوق جاهز: {path.name}",
                "artifacts": {**state.get("artifacts", {}), "report_path": str(path)},
                "progress": state.get("progress", []) + ["REPORT_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل كتابة التقرير: {e}", "progress": state.get("progress", []) + ["FAILED reporter"]}


def _market_supervisor(state: KidState) -> KidState:
    nxt = ask_supervisor("market.supervisor", state.get("progress", []),
                         [("researcher", "RESEARCH_DONE"), ("reporter", "REPORT_DONE"), ("done", None)])
    return {"summary": nxt}


def _market_route(state: KidState) -> str:
    if state.get("error"):
        return END
    return {"researcher": "researcher", "reporter": "reporter"}.get(
        (state.get("summary") or "").strip().lower(), END)


def build_market_graph():
    g = StateGraph(KidState)
    g.add_node("supervisor", _market_supervisor)
    g.add_node("researcher", _market_researcher)
    g.add_node("reporter", _market_reporter)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _market_route,
                            {"researcher": "researcher", "reporter": "reporter", END: END})
    g.add_edge("researcher", "supervisor")
    g.add_edge("reporter", "supervisor")
    return g.compile()


# ======================================================================
# مشرف المحتوى
# ======================================================================
def _story_writer(state: KidState) -> KidState:
    store = get_store()
    idea = (state.get("idea") or state.get("task") or "").strip()
    log(store, state.get("run_id"), f"الكاتب يكتب القصة عن: {idea[:80]}")
    try:
        story = tools.write_story(idea, config.LANGUAGE, config.PAGES)
        slug = slugify(story["title"])
        book_dir = config.BOOKS_DIR / slug
        book_dir.mkdir(parents=True, exist_ok=True)
        (book_dir / "story.json").write_text(
            json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
        store.create_book(slug, story["title"], idea, config.LANGUAGE, status="story_draft")
        store.update_book(slug, page_count=len(story["pages"]))
        return {"story": story, "slug": slug,
                "progress": state.get("progress", []) + [f"STORY_DONE {slug}"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل كتابة القصة: {e}", "progress": state.get("progress", []) + ["FAILED story_writer"]}


def _illustrator(state: KidState) -> KidState:
    store = get_store()
    progress = state.get("progress", [])
    slug = state.get("slug") or next((m.split(" ", 1)[1] for m in progress
                                      if m.startswith("STORY_DONE ")), None)
    if not slug:
        return {"error": "لا توجد قصة جاهزة لتوليد الصور",
                "progress": progress + ["FAILED illustrator"]}
    log(store, state.get("run_id"), f"توليد صور الصفحات للكتاب {slug}…")
    try:
        book_dir = config.BOOKS_DIR / slug
        story = json.loads((book_dir / "story.json").read_text(encoding="utf-8"))
        imgs = tools.generate_images(story, book_dir)
        store.update_book(slug, status="images_ready")
        return {"slug": slug, "story": story,
                "artifacts": {**state.get("artifacts", {}), "images": imgs},
                "progress": progress + [f"IMAGES_DONE {slug}"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل توليد الصور: {e}", "progress": progress + ["FAILED illustrator"]}


def _pdf_builder(state: KidState) -> KidState:
    store = get_store()
    progress = state.get("progress", [])
    slug = state.get("slug") or next((m.split(" ", 1)[1] for m in progress
                                      if m.startswith("IMAGES_DONE ")), None)
    if not slug:
        return {"error": "لا توجد صور جاهزة لبناء الـ PDF",
                "progress": progress + ["FAILED pdf_builder"]}
    log(store, state.get("run_id"), f"تجميع PDF للكتاب {slug}…")
    try:
        book_dir = config.BOOKS_DIR / slug
        story = json.loads((book_dir / "story.json").read_text(encoding="utf-8"))
        imgs = [str(p) for p in sorted(book_dir.glob("p*.png"),
                                       key=lambda p: int(re.search(r"\d+", p.stem).group()))]
        if len(imgs) != len(story["pages"]):
            raise RuntimeError(f"عدد الصور ({len(imgs)}) لا يطابق الصفحات ({len(story['pages'])})")
        pdf = book_dir / "book.pdf"
        tools.build_pdf(story, imgs, pdf)
        store.update_book(slug, status="pdf_ready", pdf_path=str(pdf),
                          cover_path=imgs[0] if imgs else None)
        return {"slug": slug, "pdf_path": str(pdf),
                "summary": f"الكتاب جاهز للمراجعة والنشر: {pdf}",
                "artifacts": {**state.get("artifacts", {}), "pdf_path": str(pdf)},
                "progress": progress + [f"PDF_DONE {slug}"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل بناء الـ PDF: {e}", "progress": progress + ["FAILED pdf_builder"]}


def _content_supervisor(state: KidState) -> KidState:
    nxt = ask_supervisor("content.supervisor", state.get("progress", []),
                         [("story_writer", "STORY_DONE"), ("illustrator", "IMAGES_DONE"),
                          ("pdf_builder", "PDF_DONE"), ("done", None)])
    return {"summary": nxt}


def _content_route(state: KidState) -> str:
    if state.get("error"):
        return END
    if state.get("stop_after") == "story" and any(
            m.startswith("STORY_DONE") for m in state.get("progress", [])):
        return END
    return {"story_writer": "story_writer",
            "illustrator": "illustrator",
            "pdf_builder": "pdf_builder"}.get(
        (state.get("summary") or "").strip().lower(), END)


def build_content_graph():
    g = StateGraph(KidState)
    g.add_node("supervisor", _content_supervisor)
    g.add_node("story_writer", _story_writer)
    g.add_node("illustrator", _illustrator)
    g.add_node("pdf_builder", _pdf_builder)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _content_route,
                            {"story_writer": "story_writer", "illustrator": "illustrator",
                             "pdf_builder": "pdf_builder", END: END})
    g.add_edge("story_writer", "supervisor")
    g.add_edge("illustrator", "supervisor")
    g.add_edge("pdf_builder", "supervisor")
    return g.compile()


# ======================================================================
# مشرف النشر
# ======================================================================
def _etsy_publisher(state: KidState) -> KidState:
    store = get_store()
    progress = state.get("progress", [])
    slug = state.get("slug") or ""
    if not slug:
        for marker in ("PDF_DONE ", "IMAGES_DONE ", "STORY_DONE "):
            hit = next((m for m in progress if m.startswith(marker)), None)
            if hit:
                slug = hit[len(marker):].strip()
                break
    slug = slug or state.get("idea", "").strip()

    # بوابة الموافقة البشرية — تُفحص من جدول kb_approvals أيضاً في app
    if not state.get("human_confirmed"):
        return {"error": "لم تُمنح الموافقة على النشر — أنشئ طلب موافقة من لوحة الموافقات أولاً",
                "progress": progress + ["FAILED etsy_publisher"]}

    book = store.get_book(slug)
    if not book:
        return {"error": f"الكتاب «{slug}» غير موجود في قاعدة البيانات",
                "progress": progress + ["FAILED etsy_publisher"]}
    if not book.get("pdf_path") or not Path(book["pdf_path"]).exists():
        return {"error": "لا يوجد ملف PDF جاهز — نفّذ البناء أولاً",
                "progress": progress + ["FAILED etsy_publisher"]}

    log(store, state.get("run_id"), f"إنشاء مسودة Etsy للكتاب {slug}…")
    try:
        story_path = config.BOOKS_DIR / slug / "story.json"
        story = json.loads(story_path.read_text(encoding="utf-8"))
        lid, is_mock = tools.etsy_create_draft(
            story["etsy"], book["pdf_path"],
            book.get("cover_path") or str(config.BOOKS_DIR / slug / "p1.png"))
        store.update_book(slug, etsy_listing_id=lid, status="draft_etsy")
        note = "مسودة تجريبية (MOCK)" if is_mock else "مسودة حقيقية على Etsy"
        return {"summary": f"{note} رقم {lid}",
                "artifacts": {**state.get("artifacts", {}), "listing_id": lid, "mock": is_mock},
                "progress": progress + [f"PUBLISH_DONE {slug}"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل الرفع على Etsy: {e}", "progress": progress + ["FAILED etsy_publisher"]}


def _publishing_supervisor(state: KidState) -> KidState:
    nxt = ask_supervisor("publishing.supervisor", state.get("progress", []),
                         [("etsy_publisher", "PUBLISH_DONE"), ("done", None)])
    return {"summary": nxt}


def _publishing_route(state: KidState) -> str:
    if state.get("error"):
        return END
    return "etsy_publisher" if (state.get("summary") or "").strip().lower() == "etsy_publisher" else END


def build_publishing_graph():
    g = StateGraph(KidState)
    g.add_node("supervisor", _publishing_supervisor)
    g.add_node("etsy_publisher", _etsy_publisher)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _publishing_route,
                            {"etsy_publisher": "etsy_publisher", END: END})
    g.add_edge("etsy_publisher", "supervisor")
    return g.compile()


# ======================================================================
# واجهة التشغيل
# ======================================================================
def run_market_domain(task: str, store, run_id=None):
    return invoke_domain(build_market_graph(), {"task": task, "run_id": run_id, "progress": []},
                         store, run_id, "تحليل السوق اكتمل")


def run_content_domain(task: str, store, run_id=None,
                       resume_from: str | None = None,
                       stop_after: str | None = None):
    state: KidState = {"task": task, "idea": task, "run_id": run_id,
                       "progress": [], "stop_after": stop_after or ""}
    if resume_from:
        state["slug"] = resume_from
        state["progress"] = [f"STORY_DONE {resume_from}"]
        state["task"] = f"build book {resume_from}"
        state["idea"] = resume_from
    return invoke_domain(build_content_graph(), state, store, run_id, "الكتاب جاهز")


def run_publishing_domain(slug: str, store, run_id=None, human_confirmed=False):
    state: KidState = {"task": f"publish {slug}", "slug": slug, "idea": slug,
                       "run_id": run_id, "human_confirmed": bool(human_confirmed),
                       "progress": [f"PDF_DONE {slug}"]}
    return invoke_domain(build_publishing_graph(), state, store, run_id, "تم إنشاء المسودة")


# ---------- التسجيل ----------
register_domain(DomainSpec(
    key="kids_books.market",
    title="الكتب — مشرف السوق",
    description="يجمع Google Trends ومنافسة Etsy ثم يصدر تقرير فرصة بالعربية",
    run=lambda task, store, run_id=None: run_market_domain(task, store, run_id),
    agents=["researcher (أداة: Trends + Etsy)", "reporter (LLM: تحليل وكتابة)",
            "supervisor (researcher → reporter → done)"],
    capabilities=["google_trends", "etsy_competition", "market_report_md"],
    keywords=["market", "trend", "السوق", "سوق", "تحليل", "niche", "منافس"],
    approval_policy="none",
))

register_domain(DomainSpec(
    key="kids_books.content",
    title="الكتب — مشرف المحتوى",
    description="يكتب القصة، يولّد صوراً بشخصية ثابتة، ويبني PDF مربع 8.5×8.5",
    run=lambda task, store, run_id=None: run_content_domain(task, store, run_id),
    agents=["story_writer (LLM: قصة JSON محققة)", "illustrator (GPT-Image / محاكاة)",
            "pdf_builder (ReportLab + Amiri)",
            "supervisor (story → images → pdf)"],
    capabilities=["write_story", "generate_images", "build_pdf"],
    keywords=["story", "book", "قصة", "كتاب", "كتاب", "انشئ", "make", "coloring"],
    approval_policy="story_review",
))

register_domain(DomainSpec(
    key="kids_books.publishing",
    title="الكتب — مشرف النشر",
    description="يرفع ملف الكتاب مسودةً على Etsy بعد موافقة بشرية صريحة من جدول الموافقات فقط",
    run=lambda slug, store, run_id=None, human_confirmed=False:
        run_publishing_domain(slug, store, run_id, human_confirmed),
    agents=["etsy_publisher (ETSY API v3 / MOCK)", "supervisor (etsy_publisher → done)"],
    capabilities=["etsy_draft_listing"],
    keywords=["publish", "انشر", "نشر", "etsy", "رفع", "kdp", "listing"],
    approval_policy="human_required",
))
