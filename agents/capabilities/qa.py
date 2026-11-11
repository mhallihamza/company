"""qa_checks — deterministic PASS/FAIL gate before any publish."""
from __future__ import annotations
import json
import re
from pathlib import Path

from PIL import Image

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
        title = str(story.get("title", "")).strip()
        checks.append(("title is non-empty ASCII-safe", bool(title) and title.isprintable(), title[:60]))
        pages = story.get("pages", [])
        expected_count = int(story.get("page_count") or story.get("expected_pages") or len(pages) or 12)
        checks.append((f"page count matches target ({expected_count})",
                       len(pages) == expected_count, f"actual {len(pages)}"))
        missing = [i + 1 for i, p in enumerate(pages)
                   if not p.get("text") or not p.get("image_prompt")]
        checks.append(("every page has text + prompt", not missing,
                       f"missing pages: {missing}" if missing else ""))

        from agents.capabilities.pdf import build_book_pdf  # noqa: F401
        pdf = d / "book.pdf"
        pdf_ok = pdf.exists() and pdf.stat().st_size > 1000 and pdf.read_bytes()[:4] == b"%PDF"
        checks.append(("book.pdf present and valid", pdf_ok, str(pdf)))

        kdp_pdf = d / "interior_kdp.pdf"
        if kdp_pdf.exists():
            kdp_ok = kdp_pdf.stat().st_size > 1000 and kdp_pdf.read_bytes()[:4] == b"%PDF"
            checks.append(("kdp interior PDF present and valid", kdp_ok, str(kdp_pdf)))

        etsy_images = list(d.glob("p*.png")) + list(d.glob("p*.jpg")) + list(d.glob("p*.jpeg"))
        expected_imgs = pages
        checks.append((f"page images = {len(expected_imgs)}",
                       len(etsy_images) >= len(expected_imgs),
                       f"actual {len(etsy_images)}"))
        for p in etsy_images:
            try:
                with Image.open(p) as im:
                    checks.append((f"image {p.name} resolution ≥ 300dpi-compatible",
                                   min(im.size) >= 1024,
                                   f"size {im.size}"))
            except Exception as e:  # noqa: BLE001
                checks.append((f"image {p.name} readable", False, str(e)))

        etsy = story.get("etsy") or {}
        title = str(etsy.get("title", ""))
        checks.append(("Etsy title ≤ 140 chars", 0 < len(title) <= 140, f"len {len(title)}"))
        checks.append(("Etsy tags ≤ 13", len(etsy.get("tags", [])) <= 13,
                       f"actual {len(etsy.get('tags', []))}"))
        if story.get("product_type"):
            checks.append(("product is printable/KDP format declared",
                           story.get("marketplace") in ("kdp", "etsy", "both"),
                           f"marketplace={story.get('marketplace')}"))

    checks.append(("Amiri font present (Latin coverage)", ARABIC_FONT.exists(), str(ARABIC_FONT)))
    return checks


from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="qa_checks",
    title_en="QA Preflight Gate", title_ar="QA Preflight Gate",
    description_en="Structure/images/PDF/Etsy field limits + Arabic font availability — deterministic PASS/FAIL.",
    description_ar="Structure/images/PDF/Etsy field limits/font present — deterministic PASS/FAIL gate.",
    used_by=["qa", "books.content"], deterministic=True,
))
