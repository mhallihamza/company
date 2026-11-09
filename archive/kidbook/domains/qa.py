"""قسم الجودة والامتثال — بوابة حتمية قبل أي نشر أو تسليم.

يفحص: بنية story.json، عدد الصفحات والصور، سلامة PDF وملف الخط العربي،
قيود طول حقول Etsy (عنوان ≤ 140، وسوم ≤ 13). النتيجة: تقرير PASS/FAIL محفوظ.
"""
from __future__ import annotations
import json
import re
from datetime import date
from pathlib import Path

from langgraph.graph import StateGraph, START, END

from kidbook import config
from kidbook.db import get_store
from kidbook.domains import DomainSpec, register_domain
from kidbook.domains.common import KidState, invoke_domain, ask_supervisor, log


def check_book(slug: str) -> list[tuple[str, bool, str]]:
    d = config.BOOKS_DIR / slug
    checks: list[tuple[str, bool, str]] = []

    story_file = d / "story.json"
    checks.append(("story.json موجود", story_file.exists(), str(story_file)))

    story = None
    if story_file.exists():
        try:
            story = json.loads(story_file.read_text(encoding="utf-8"))
            checks.append(("story.json صالح (JSON)", True, ""))
        except Exception as e:  # noqa: BLE001
            checks.append(("story.json صالح (JSON)", False, str(e)))

    if story:
        for key in ("title", "character_sheet", "style", "pages", "etsy"):
            checks.append((f"الحقل المطلوب {key}", key in story, ""))
        pages = story.get("pages", [])
        checks.append((f"عدد الصفحات = {config.PAGES}", len(pages) == config.PAGES,
                       f"الحالي {len(pages)}"))
        missing = [i + 1 for i, p in enumerate(pages)
                   if not p.get("text") or not p.get("image_prompt")]
        checks.append(("كل صفحة فيها نص ووصف رسم", not missing,
                       f"الصفحات الناقصة: {missing}" if missing else ""))
        pdf = d / "book.pdf"
        pdf_ok = pdf.exists() and pdf.stat().st_size > 1000 and \
            pdf.read_bytes()[:4] == b"%PDF"
        checks.append(("book.pdf موجود وسليم (magic %PDF)", pdf_ok, str(pdf)))
        pngs = sorted(d.glob("p*.png"))
        checks.append((f"صور الصفحات = {len(pages)}", len(pngs) == len(pages),
                       f"الحالي {len(pngs)}"))
        title = str((story.get("etsy") or {}).get("title", ""))
        checks.append(("عنوان Etsy ≤ 140 حرفاً", 0 < len(title) <= 140, f"الطول {len(title)}"))
        tags = (story.get("etsy") or {}).get("tags", [])
        checks.append(("وسوم Etsy ≤ 13", len(tags) <= 13, f"الحالي {len(tags)}"))
    checks.append(("الخط العربي Amiri متوفر للطباعة", config.ARABIC_FONT.exists(),
                   str(config.ARABIC_FONT)))
    return checks


def _checker(state: KidState) -> KidState:
    store = get_store()
    slug = (state.get("task") or "").strip().split()[-1] if state.get("task") else ""
    if not slug or not (config.BOOKS_DIR / slug).exists():
        books = sorted((p.name for p in config.BOOKS_DIR.iterdir() if p.is_dir()),
                       key=lambda n: (config.BOOKS_DIR / n).stat().st_mtime, reverse=True)
        slug = books[0] if books else ""
    if not slug:
        return {"error": "لا يوجد كتب للفحص", "progress": state.get("progress", []) + ["FAILED checker"]}

    log(store, state.get("run_id"), f"فحص الجودة للكتاب {slug}…")
    checks = check_book(slug)
    passed = sum(1 for _, ok, _ in checks if ok)
    verdict = "PASS ✅" if passed == len(checks) else "FAIL ❌"

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORTS_DIR / f"qa_{slug}_{date.today()}.md"
    lines = [f"### تقرير الجودة — {slug} — {date.today()}", "", f"**الحكم: {verdict}** ({passed}/{len(checks)})", ""]
    for name, ok, detail in checks:
        lines.append(f"- {'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""))
    out.write_text("\n".join(lines), encoding="utf-8")
    try:
        store.add_report(str(out), out.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    log(store, state.get("run_id"), f"الحكم النهائي: {verdict}")
    return {"summary": f"{verdict} — {passed}/{len(checks)} فحص — {out.name}",
            "artifacts": {**state.get("artifacts", {}), "qa_report": str(out), "verdict": verdict},
            "progress": state.get("progress", []) + ["CHECKS_DONE"]}


def _supervisor(state: KidState) -> KidState:
    nxt = ask_supervisor("qa.supervisor", state.get("progress", []),
                         [("checker", "CHECKS_DONE"), ("done", None)])
    return {"summary": nxt}


def _route(state: KidState) -> str:
    if state.get("error"):
        return END
    return "checker" if (state.get("summary") or "").strip().lower() == "checker" else END


def build_graph():
    g = StateGraph(KidState)
    g.add_node("supervisor", _supervisor)
    g.add_node("checker", _checker)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {"checker": "checker", END: END})
    g.add_edge("checker", "supervisor")
    return g.compile()


def run(task, store, run_id=None):
    return invoke_domain(build_graph(),
                         {"task": task, "run_id": run_id, "progress": []},
                         store, run_id, "فحص الجودة اكتمل")


register_domain(DomainSpec(
    key="qa",
    title="الجودة والامتثال",
    description="بوابة حتمية قبل النشر: البنية، الصور، سلامة PDF، حدود حقول Etsy، الخط العربي",
    run=run,
    agents=["checker (حتمي: قائمة فحص + حكم PASS/FAIL)",
            "supervisor (checker → done)"],
    capabilities=["story_validation", "pdf_integrity", "etsy_limits", "preflight_gate"],
    keywords=["qa", "جودة", "فحص", "امتثال", "preflight", "تحقق"],
    approval_policy="gate",
))
