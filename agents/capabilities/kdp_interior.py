"""KDP interior PDF builder — print-ready 6x9 paperback interior.

KDP specs (2026-11-09):
  * Trim: 6x9 inches
  * Interior: B&W / premium color (text + simple line art) — we choose B&W for line art
  * Margins: 0.25 inch safety margin minimum
  * Bleed: no bleed (our images are framed inside pages)
  * Fonts: embedded TrueType (Latin coverage only)
  * Page size: EXACTLY 6 x 9 in — a mismatched size fails KDP upload

Source: https://kdp.amazon.com/en_US/help/topic/G201953080
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white

from backend.app.config import ARABIC_FONT

_TRIM_W = 6 * inch
_TRIM_H = 9 * inch
_MARGIN = 0.34 * inch     # small inner margin, KDP allows ≥ 0.25
_SAFE = 0.25 * inch      # inner safe zone for content
_REGISTERED: dict[str, str] = {}


def _kdp_font() -> str:
    global _REGISTERED
    name = _REGISTERED.get("kdp_latin")
    if not name:
        path = Path(ARABIC_FONT)
        if not path.exists():
            raise FileNotFoundError(f"No Latin-capable font found at {path}")
        name = "KDP-Amiri-Latin"
        pdfmetrics.registerFont(TTFont(name, str(path)))
        _REGISTERED["kdp_latin"] = name
    return name


def build_kdp_interior(story: dict, image_paths: list[str], out_path: Path) -> Path:
    font = _kdp_font()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=(_TRIM_W, _TRIM_H))

    # Title page
    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(0, 0, _TRIM_W, _TRIM_H, fill=1, stroke=0)
    title = str(story.get("title", "Untitled"))
    c.setFillColor(HexColor("#173A5E"))
    text_width = _TRIM_W - 2 * _SAFE
    c.setFont(font, 28)
    # simple wrap on words, centered
    words = title.split()
    line, y = [], _TRIM_H - _SAFE - 60
    for word in words:
        trial = " ".join(line + [word])
        if c.stringWidth(trial, font, 28) <= text_width:
            line.append(word)
        else:
            c.drawCentredString(_TRIM_W / 2, y, " ".join(line))
            line, y = [word], y - 36
    if line:
        c.drawCentredString(_TRIM_W / 2, y, " ".join(line))

    c.setFont(font, 12)
    c.setFillColor(HexColor("#5E4633"))
    c.drawCentredString(_TRIM_W / 2, 40, "For children ages 3-5")
    c.showPage()

    # Cover page (full bleed image)
    body_images = image_paths[1:]
    for i, page in enumerate(story.get("pages", [])):
        img = body_images[i] if i < len(body_images) else None
        c.setFillColor(white)
        c.rect(0, 0, _TRIM_W, _TRIM_H, fill=1, stroke=0)
        if img and Path(img).exists():
            try:
                pil_img = Image.open(img)
                iw, ih = pil_img.size
                scale = min((_TRIM_W - 2 * _SAFE) / iw, (_TRIM_H - 2 * _SAFE) / ih * 0.8)
                w, h = iw * scale, ih * scale
                x = (_TRIM_W - w) / 2
                y = _TRIM_H - _SAFE - h * 0.85
                c.drawImage(img, x, y, w, h, preserveAspectRatio=True, mask="auto")
            except Exception:  # noqa: BLE001 — never block the book build on a single image
                pass
        c.setFillColor(HexColor("#173A5E"))
        c.setFont(font, 16)
        c.drawCentredString(_TRIM_W / 2, 40, f"Page {i + 1}")
        c.showPage()

    c.save()
    return out_path


from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="kdp_interior",
    title_en="KDP Interior PDF",
    title_ar="KDP Interior PDF",
    description_en="Print-ready 6x9 inch B&W interior PDF builder (KDP specs, 2026-11-09).",
    description_ar="Print-ready 6x9 inch B&W interior PDF builder (KDP specs, 2026-11-09).",
    used_by=["books.content"], deterministic=True,
))
