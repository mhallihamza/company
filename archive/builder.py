from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from config import LANGUAGE, PAGE_SIZE_IN, ARABIC_FONT
import arabic_reshaper
from bidi.algorithm import get_display

FONT = "Helvetica"

def _setup_font():
    global FONT
    if LANGUAGE == "ar":
        pdfmetrics.registerFont(TTFont("AR", ARABIC_FONT)); FONT = "AR"

def _shape(t):
    return get_display(arabic_reshaper.reshape(t)) if LANGUAGE == "ar" else t

def build_pdf(story, img_paths, out_pdf):
    _setup_font()
    S = PAGE_SIZE_IN * inch
    c = canvas.Canvas(out_pdf, pagesize=(S, S))
    def text_block(txt, size, y_top):
        lines = simpleSplit(txt, FONT, size, S - 1.5 * inch)
        y = y_top
        for ln in lines:
            if LANGUAGE == "ar":
                c.drawRightString(S - 0.75 * inch, y, _shape(ln))
            else:
                c.drawString(0.75 * inch, y, ln)
            y -= size * 1.5
    c.setFont(FONT, 34)
    c.drawCentredString(S / 2, S / 2, _shape(story["title"])); c.showPage()
    for p, img in zip(story["pages"], img_paths):
        c.drawImage(img, 0.5 * inch, 2.2 * inch, S - inch, S - 2.7 * inch, preserveAspectRatio=True)
        c.setFont(FONT, 20); text_block(p["text"], 20, 1.6 * inch); c.showPage()
    c.save()
