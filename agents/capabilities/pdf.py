"""PDF build — 8.5×8.5 children's book with the Arabic Amiri font and RTL layout."""
from __future__ import annotations
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import inch
from reportlab.lib.units import inch as IN
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from backend.app.config import ARABIC_FONT

_PAGE = 8.5 * IN
_REGISTERED: dict[str, str] = {}


def _font(font_path: Path | str | None = None) -> str:
    """Register and return the font to use. Defaults to the bundled Arabic font (Amiri)."""
    global _REGISTERED
    path = Path(font_path) if font_path else Path(ARABIC_FONT)
    key = str(path).lower()
    name = _REGISTERED.get(key)
    if not name:
        if not path.exists():
            raise FileNotFoundError(f"Font not found at {path}")
        name = "HQFont-" + path.stem.replace(" ", "_")[:40]
        pdfmetrics.registerFont(TTFont(name, str(path)))
        _REGISTERED[key] = name
    return name


def _wrap_rtl(text: str, font_name: str, size: float, max_width: float) -> list[str]:
    """Wraps Arabic text to the line width (simple and deterministic)."""
    words = str(text).split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if pdfmetrics.stringWidth(trial, font_name, size) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def build_book_pdf(story: dict, image_paths: list[str], out_path: Path,
                   *, font_path: Path | str | None = None,
                   language: str = "ar",
                   text_direction: str = "rtl") -> Path:
    font = _font(font_path)
    subtitle = {"en": "Illustrated English story",
                "fr": "Album illustré français",
                "en": "Illustrated English book"}.get(language, "Illustrated book")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=(_PAGE, _PAGE))

    # cover page
    c.setFillColor(HexColor("#FFD166"))
    c.rect(0, 0, _PAGE, _PAGE, fill=1, stroke=0)
    if image_paths and Path(image_paths[0]).exists():
        _draw_image_cover(c, image_paths[0])
    c.setFillColor(HexColor("#173A5E"))
    c.setFont(font, 34) if font else c.setFont("Helvetica-Bold", 34)
    for i, line in enumerate(_wrap_rtl(story.get("title", "Story"), font, 34, _PAGE - 1.2 * IN)):
        c.drawCentredString(_PAGE / 2, _PAGE - 0.9 * IN - i * 0.62 * IN, line)
    c.setFont(font, 16) if font else c.setFont("Helvetica", 16)
    c.setFillColor(HexColor("#7A3B2E"))
    c.drawCentredString(_PAGE / 2, 0.75 * IN, subtitle)
    c.showPage()

    body_images = image_paths[1:]
    for i, page in enumerate(story.get("pages", [])):
        c.setFillColor(white)
        c.rect(0, 0, _PAGE, _PAGE, fill=1, stroke=0)
        if i < len(body_images) and Path(body_images[i]).exists():
            try:
                img = Image.open(body_images[i])
                iw, ih = img.size
                scale = min((_PAGE - 0.6 * IN) / iw, (_PAGE - 2.2 * IN) / ih)
                w, h = iw * scale, ih * scale
                c.drawImage(body_images[i], (_PAGE - w) / 2, _PAGE - 0.4 * IN - h,
                            w, h, mask="auto")
            except Exception:  # noqa: BLE001
                pass
        c.setFillColor(HexColor("#173A5E"))
        c.setFont(font, 17) if font else c.setFont("Helvetica", 17)
        y = 1.35 * IN
        for line in _wrap_rtl(page.get("text", ""), font, 17, _PAGE - 1.1 * IN):
            c.drawCentredString(_PAGE / 2, y, line)
            y -= 0.32 * IN
        c.setFillColor(HexColor("#B08968"))
        c.setFont(font, 11) if font else c.setFont("Helvetica", 11)
        c.drawString(0.4 * IN, 0.35 * IN, str(i + 1))
        c.showPage()
    c.save()
    return out_path


def _draw_image_cover(c, path: str) -> None:
    try:
        img = Image.open(path)
        iw, ih = img.size
        scale = min((_PAGE - 0.8 * IN) / iw, (_PAGE - 1.9 * IN) / ih)
        w, h = iw * scale, ih * scale
        c.drawImage(path, (_PAGE - w) / 2, 1.0 * IN, w, h, mask="auto")
    except Exception:  # noqa: BLE001
        pass

from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="pdf_generation",
    title_en="PDF Generation", title_ar="PDF Generation",
    description_en="8.5×8.5 inch RTL Arabic PDF with Amiri font (children's print format).",
    description_ar="8.5x8.5 inch LTR print PDF using Amiri (Latin coverage) — children's print format.",
    used_by=["books.content"], deterministic=True,
))
