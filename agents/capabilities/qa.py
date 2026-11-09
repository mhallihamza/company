"""qa_checks — بوابة PASS/FAIL الحتمية قبل أي نشر."""
from __future__ import annotations
import json
from pathlib import Path

from backend.app.config import ARABIC_FONT, BOOKS_DIR


def check_product(slug: str) -> list[tuple[str, bool, str]]:
    d = BOOKS_DIR / slug
    checks: list[tuple[str, bool, str]] = []

    story_file = d / "story.json"
    checks.append(("story.json exists", story_file.exists(), str(story_file)))

    story = None
    if story_file.exists():
        try:
            story = json.loads(story_file.read_text(encoding="utf-8"))
            checks.append(("story.json is valid JSON", True, ""))
        except Exception as e:  # noqa: BLE001
            checks.append(("story.json is valid JSON", False, str(e)))

    if story:
        for key in ("title", "character_sheet", "style", "pages", "etsy"):
            checks.append((f"required field {key}", key in story, ""))
        pages = story.get("pages", [])
        checks.append(("page count = 12", len(pages) == 12, f"actual {len(pages)}"))
        missing = [i + 1 for i, p in enumerate(pages)
                   if not p.get("text") or not p.get("image_prompt")]
        checks.append(("every page has text + prompt", not missing,
                       f"missing pages: {missing}" if missing else ""))
        from agents.capabilities.pdf import build_book_pdf  # noqa: F401 — نضمن وجود البناء
        pdf = d / "book.pdf"
        pdf_ok = pdf.exists() and pdf.stat().st_size > 1000 and pdf.read_bytes()[:4] == b"%PDF"
        checks.append(("book.pdf present and valid", pdf_ok, str(pdf)))
        import re
        pngs = [p for p in d.glob("p*.png") if re.match(r"p([1-9]\d*)\.png$", p.name)]
        checks.append((f"page images = {len(pages)}", len(pngs) == len(pages), f"actual {len(pngs)}"))
        etsy = story.get("etsy") or {}
        title = str(etsy.get("title", ""))
        checks.append(("Etsy title ≤ 140 chars", 0 < len(title) <= 140, f"len {len(title)}"))
        checks.append(("Etsy tags ≤ 13", len(etsy.get("tags", [])) <= 13,
                       f"actual {len(etsy.get('tags', []))}"))
    checks.append(("Amiri Arabic font present", ARABIC_FONT.exists(), str(ARABIC_FONT)))
    return checks


from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="qa_checks",
    title_en="QA Preflight Gate", title_ar="بوابة فحص الجودة",
    description_en="Structure/images/PDF/Etsy field limits + Arabic font availability — deterministic PASS/FAIL.",
    description_ar="بنية/صور/PDF/حدود حقول Etsy/توفّر الخط العربي — حكم حتمي PASS/FAIL.",
    used_by=["qa", "books.content"], deterministic=True,
))
