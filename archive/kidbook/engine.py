"""المحرك — CEO Orchestrator والواجهة البرمجية للمشروع كله.

يربط المهمة الحرة بالقسم الأنسب من kidbook.domains.DOMAIN_REGISTRY،
ويوثّق كل تشغيلة في قاعدة البيانات، وينصّب بوابة موافقة بشرية صريحة
قبل أي إجراء خارجي (رفع مسودات Etsy) عبر kidbook_approvals.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from kidbook import config
from kidbook.db import get_store
from kidbook.domains import DOMAIN_REGISTRY
from kidbook.domains import affiliate, finance, intelligence, kids_books, marketing, qa  # noqa: F401 — تسجيل
from kidbook.domains.common import DomainError
from kidbook.llm import get_chat_model


def _new_run(store, run_type: str, domain: str, ref: str | None):
    rid = store.create_run(run_type, domain=domain, ref=(ref or "")[:300])
    store.log(rid, f"بدء التشغيلة ({run_type}) — {ref or ''}")
    return rid


def _finish_ok(store, rid, summary):
    store.log(rid, f"اكتمل: {summary}")
    return {"ok": True, "run_id": rid, "summary": summary}


def _finish_fail(store, rid, err):
    store.log(rid, str(err), "error")
    return {"ok": False, "run_id": rid, "error": str(err)}


# ---------------- التوجيه ----------------
def _keyword_route(text: str) -> str | None:
    text = text.lower()
    best, best_score = None, 0
    for spec in DOMAIN_REGISTRY.values():
        # وزن كل كلمة بطولها: قائمة طويلة أدقّ من مصادفة قصيرة («trend» تفوق «etsy»)
        score = sum(len(kw) for kw in spec.keywords if kw.lower() in text)
        if score > best_score:
            best, best_score = spec.key, score
    return best


def route_task(task: str) -> str:
    """يختار القسم الأنسب. LLM في الحالة الحية وكلمات مفتاحية مسجلة في المحاكاة."""
    try:
        model = get_chat_model(temperature=0, max_tokens=100)
        sys = ("[ROLE:orchestrator]\nYou are the CEO/Orchestrator of a children's-book & affiliate business.\n"
               f"Available departments (key — what they do):\n"
               + "\n".join(f"- {s.key} — {s.description}" for s in DOMAIN_REGISTRY.values())
               + '\nReply ONLY JSON: {"domain": "<exact key>"}')
        raw = model.invoke([SystemMessage(content=sys),
                            HumanMessage(content=task)]).content
        domain = json.loads(re.search(r"\{.*?\}", str(raw), re.S).group(0))["domain"]
        if domain in DOMAIN_REGISTRY:
            return domain
    except Exception:  # noqa: BLE001
        pass
    return _keyword_route(task) or "kids_books.content"


# ---------------- واجهات الأقسام ----------------
def _run_domain(run_type, domain_key, ref, fn):
    config.ensure_dirs()
    store = get_store()
    rid = _new_run(store, run_type, domain_key, ref)
    try:
        result = fn(store, rid)
        summary = getattr(result, "get", lambda *_: None)("summary") or "اكتمل"
        artifacts = (result.get("artifacts") or {}) if isinstance(result, dict) else {}
        out = _finish_ok(store, rid, summary)
        out.update(artifacts)
        return out
    except (DomainError, Exception) as e:  # noqa: BLE001
        try:
            return _finish_fail(store, rid, e)
        except Exception:
            return {"ok": False, "run_id": rid, "error": str(e)}


def analyze_market() -> dict[str, Any]:
    return _run_domain("market_report", "kids_books.market", "تقرير الاتجاهات",
                       lambda s, r: kids_books.run_market_domain(
                           "تحليل السوق الأسبوعي", s, r))


def create_story(idea: str) -> dict[str, Any]:
    config.ensure_dirs()
    store = get_store()
    idea = (idea or "").strip()
    if not idea:
        return {"ok": False, "error": "الفكرة فارغة"}
    rid = _new_run(store, "make_story", "kids_books.content", idea)
    try:
        result = kids_books.run_content_domain(idea, store, rid, stop_after="story")
        story_path = config.BOOKS_DIR / result["slug"] / "story.json"
        summary = f"القصة جاهزة للمراجعة: {story_path}"
        store.log(rid, summary)
        return {"ok": True, "run_id": rid, "slug": result["slug"],
                "story": result.get("story"), "story_path": str(story_path),
                "summary": summary}
    except Exception as e:  # noqa: BLE001
        return _finish_fail(store, rid, e)


def build_book(slug: str) -> dict[str, Any]:
    config.ensure_dirs()
    store = get_store()
    slug = (slug or "").strip()
    if not (config.BOOKS_DIR / slug / "story.json").exists():
        return {"ok": False, "error": f"لا توجد قصة لـ «{slug}» — نفّذ المرحلة الأولى أولاً"}
    rid = _new_run(store, "build_book", "kids_books.content", slug)
    try:
        edits = json.loads((config.BOOKS_DIR / slug / "story.json").read_text(encoding="utf-8"))
        if not edits.get("title") or not edits.get("pages"):
            raise ValueError("story.json لا يحتوي عنواناً أو صفحات — راجع الملف")
        result = kids_books.run_content_domain(slug, store, rid, resume_from=slug)
        pdf = (result.get("artifacts") or {}).get("pdf_path") or result.get("pdf_path")
        store.log(rid, f"الكتاب جاهز: {pdf}")
        return {"ok": True, "run_id": rid, "slug": slug, "pdf_path": pdf,
                "summary": result.get("summary")}
    except Exception as e:  # noqa: BLE001
        return _finish_fail(store, rid, e)


def run_intelligence(brief: str = "") -> dict[str, Any]:
    return _run_domain("intelligence_scan", "intelligence", brief or "مسح الفرص",
                       lambda s, r: intelligence.run(brief or "مسح الفرص العام", s, r))


def run_affiliate(niche: str = "") -> dict[str, Any]:
    return _run_domain("affiliate_scan", "affiliate", niche or "منتجات بالعمولة",
                       lambda s, r: affiliate.run(niche or "منتجات مناسبة لنشر كتب الأطفال", s, r))


def run_marketing(brief: str) -> dict[str, Any]:
    return _run_domain("marketing_pack", "marketing", brief,
                       lambda s, r: marketing.run(brief, s, r))


def run_finance(brief: str = "") -> dict[str, Any]:
    return _run_domain("finance_analysis", "finance", brief or "افتراضيات 4.99 و12 صفحة",
                       lambda s, r: finance.run(brief or "book 4.99 usd 24 pages", s, r))


def run_qa(slug: str = "") -> dict[str, Any]:
    return _run_domain("qa_check", "qa", slug or "أحدث كتاب",
                       lambda s, r: qa.run(slug or "", s, r))


# ---------------- بوابة الموافقة على النشر ----------------
def request_publish(slug: str, note: str = "") -> dict[str, Any]:
    """ينشئ طلب موافقة شفافاً — لا يلمس Etsy إطلاقاً حتى يُعتمد."""
    config.ensure_dirs()
    store = get_store()
    slug = (slug or "").strip()
    book = store.get_book(slug)
    if not book:
        return {"ok": False, "error": f"الكتاب «{slug}» غير موجود"}
    if not (book.get("pdf_path") and Path(book["pdf_path"]).exists()):
        return {"ok": False, "error": "لا يوجد PDF جاهز — ابنِ الكتاب أولاً"}
    rid = _new_run(store, "request_publish", "kids_books.publishing", slug)
    aid = store.create_approval("etsy_publish", slug, note or f"طلب رفع مسودة Etsy لـ {slug}")
    store.log(rid, f"أُنشئ طلب موافقة رقم {aid} للكتاب {slug}")
    return {"ok": True, "run_id": rid, "approval_id": aid, "status": "pending"}


def decide_publish(approval_id: int, decision: str, note: str = "") -> dict[str, Any]:
    """يعتمد أو يرفض طلباً؛ عند الاعتماد ينفَّذ الرفع (أو MOCK) كوسيط بعد التوثيق."""
    config.ensure_dirs()
    store = get_store()
    approval = store.get_approval(approval_id)
    if not approval:
        return {"ok": False, "error": f"لا يوجد طلب موافقة رقم {approval_id}"}
    if approval["status"] != "pending":
        return {"ok": False, "error": f"الطلب #{approval_id} محسوم بالفعل ({approval['status']})"}
    decision = (decision or "").lower()
    slug = approval["ref"]

    if decision == "reject":
        store.decide_approval(approval_id, "rejected", note)
        rid = _new_run(store, "publish_rejected", "kids_books.publishing", slug)
        store.log(rid, f"رُفض النشر — {note or 'بدون ملاحظة'}")
        store.finish_run(rid, "success", "مرفوض بقرار بشري")
        return {"ok": True, "approval_id": approval_id, "decision": "rejected"}

    if decision != "approve":
        return {"ok": False, "error": "decision يجب أن تكون approve أو reject"}

    store.decide_approval(approval_id, "approved", note)
    rid = _new_run(store, "publish_approved", "kids_books.publishing", slug)
    try:
        result = kids_books.run_publishing_domain(slug, store, rid, human_confirmed=True)
        artifacts = result.get("artifacts") or {}
        store.log(rid, f"نُشرت مسودة بعد موافقة #{approval_id}: {artifacts.get('listing_id')}")
        return {"ok": True, "approval_id": approval_id, "decision": "approved",
                "listing_id": artifacts.get("listing_id"), "mock": bool(artifacts.get("mock"))}
    except Exception as e:  # noqa: BLE001
        store.log(rid, str(e), "error")
        store.finish_run(rid, "failed", str(e))
        return {"ok": False, "run_id": rid, "error": str(e)}


def publish_book(slug: str, human_confirmed: bool = False) -> dict[str, Any]:
    """الرفع الصريح: إما تأكيد بشري مباشر أو الرفض — لا مسار غامض."""
    config.ensure_dirs()
    store = get_store()
    slug = (slug or "").strip()
    if not human_confirmed:
        return {"ok": False,
                "error": "النشر يتطلب موافقة بشرية صريحة — استدعِ request_publish "
                         "ثم decide_publish، أو مرر human_confirmed=True"}
    if not store.get_book(slug):
        return {"ok": False, "error": f"الكتاب «{slug}» غير موجود"}
    aid = store.create_approval("etsy_publish", slug, "موافقة فورية عبر التأكيد المباشر")
    out = decide_publish(aid, "approve", "موافقة فورية (human-confirmed)")
    out["slug"] = slug
    return out


# ---------------- CEO للمحادثات الحرة ----------------
def run_task(text: str) -> dict[str, Any]:
    domain = route_task(text)
    handlers = {
        "kids_books.market": lambda: analyze_market(),
        "kids_books.content": lambda: create_story(text),
        "kids_books.publishing": lambda: {
            "ok": False, "domain": domain,
            "error": "النشر يتطلب موافقة صريحة عبر تبويب الموافقات أو طلب نشر (publish <slug>)"},
        "intelligence": lambda: run_intelligence(text),
        "affiliate": lambda: run_affiliate(text),
        "marketing": lambda: run_marketing(text),
        "finance": lambda: run_finance(text),
        "qa": lambda: run_qa(text.split()[-1] if text.split() else ""),
    }
    out = handlers.get(domain, lambda: create_story(text))()
    out["domain"] = domain
    return out
