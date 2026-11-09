"""أدوات الوكلاء: اتجاهات السوق، كتابة القصة، الصور، الـ PDF، والنشر.

كل أداة مسؤولة عن شيء واحد وقابلة للاختبار منفردة. في وضع المحاكاة
(KIDBOOK_FAKE_LLM=1) تُرجع الأدوات الخارجية بيانات ثابتة بدل الاتصال.
"""
from __future__ import annotations
import base64
import datetime as _dt
import json
import os
import re
from pathlib import Path

import requests

from kidbook import config

# ---------------- أدوات البيانات ----------------

def google_trends(keywords):
    """متوسط الاهتمام وتغيره لكل كلمة. عند الفشل في الوضع التجريبي ترجع بيانات تجريبية."""
    if config.FAKE_LLM:
        return {kw: {"avg": round(20 + (hash(kw) % 60) + 0.5, 1),
                     "last_vs_first": round(((hash(kw) % 41) - 20) + 0.5, 1),
                     "mock": True} for kw in keywords}
    from pytrends.request import TrendReq
    out = {}
    py = TrendReq(hl="en-US", tz=0)
    for kw in keywords:
        try:
            py.build_payload([kw], timeframe="today 3-m")
            df = py.interest_over_time()
            if df is not None and not df.empty:
                s = df[kw]
                out[kw] = {"avg": round(float(s.mean()), 1),
                           "last_vs_first": round(float(s.iloc[-4:].mean() - s.iloc[:4].mean()), 1)}
            else:
                out[kw] = {"avg": None, "last_vs_first": None}
        except Exception as e:  # noqa: BLE001
            out[kw] = {"error": str(e)}
    return out


def etsy_competition(keywords):
    """عدد المنافسين وإحصائياتهم من Etsy Open API v3. {} عند غياب المفتاح."""
    key = os.getenv("ETSY_API_KEY")
    if not key:
        if config.FAKE_LLM:
            return {kw: {"total_listings": 100 + hash(kw) % 900,
                         "avg_favorers_top25": 50 + hash(kw[::-1]) % 400,
                         "avg_price": 4.99, "mock": True} for kw in keywords}
        return {}
    out = {}
    for kw in keywords:
        r = requests.get("https://openapi.etsy.com/v3/application/listings/active",
                         headers={"x-api-key": key},
                         params={"keywords": kw, "limit": 25, "sort_on": "score"}, timeout=30)
        if r.ok:
            j = r.json()
            res = j.get("results", [])
            out[kw] = {
                "total_listings": j.get("count"),
                "avg_favorers_top25": round(sum(x.get("num_favorers", 0) for x in res) / max(len(res), 1), 1),
                "avg_price": round(sum(float(x["price"]["amount"]) / x["price"]["divisor"]
                                       for x in res) / max(len(res), 1), 2) if res else None,
            }
        else:
            out[kw] = {"error": f"HTTP {r.status_code}"}
    return out


def full_research(keywords):
    return {"google_trends": google_trends(keywords),
            "etsy_competition": etsy_competition(keywords),
            "sampled_at": _dt.datetime.now().isoformat(timespec="seconds")}


# ---------------- كتابة القصة ----------------

def json_extract(txt: str):
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    if not txt.startswith("{"):
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            raise ValueError("النموذج لم يُرجع JSON")
        txt = m.group(0)
    return json.loads(txt)


def validate_story(data: dict, pages: int) -> dict:
    if not isinstance(data, dict):
        raise ValueError("صيغة القصة غير صالحة")
    for key in ("title", "character_sheet", "style", "pages", "etsy"):
        if key not in data:
            raise ValueError(f"الحقل المطلوب مفقود: {key}")
    if not isinstance(data["pages"], list) or len(data["pages"]) != pages:
        raise ValueError(f"عدد الصفحات المطلوب {pages} وليس {len(data.get('pages', []))}")
    for i, p in enumerate(data["pages"], 1):
        if not p.get("text") or not p.get("image_prompt"):
            raise ValueError(f"الصفحة {i} تفتقد نصاً أو وصف رسم")
    etsy = data["etsy"]
    etsy.setdefault("tags", [])
    etsy["tags"] = [str(t)[:20] for t in etsy["tags"][:13]]
    return data


def write_story(idea: str, language: str, pages: int, system_tag: str = "[ROLE:story_writer]"):
    from kidbook.llm import get_chat_model
    from langchain_core.messages import SystemMessage, HumanMessage

    lang = "Modern Standard Arabic (simple, fully vowel-free but clear)" if language == "ar" else "English"
    model = get_chat_model(temperature=0.7, max_tokens=6000)
    system = (f"{system_tag}\nYou write picture books for children aged {config.AGE_RANGE} in {lang}. "
              f"IDEA: {idea}\nPAGES: {pages}\n"
              f"Rules: exactly {pages} pages; 1-3 short sentences per page; positive values; "
              f"nothing scary; no text inside images; 13 short Etsy tags.\n"
              f"Return ONLY JSON with keys: title, character_sheet (detailed FIXED visual description), "
              f"style (one fixed art-style sentence), pages[{{text,image_prompt}}], "
              f"etsy{{title,description,tags[13]}}.")
    raw = model.invoke([SystemMessage(content=system),
                        HumanMessage(content=f"اكتب قصة عن: {idea}")]).content
    return validate_story(json_extract(raw), pages)


# ---------------- الصور ----------------

def _mock_image(path: Path, page_no: int, title: str):
    """صورة تجريبية: سماء متدرجة وجبل وشمس — لا نص عربي حتى لا يتشوّه."""
    from PIL import Image, ImageDraw
    W = H = 1024
    img = Image.new("RGB", (W, H))
    top, bottom = (135 + page_no * 7 % 60, 206, 250), (255, 244, 214)
    for y in range(H):
        t = y / H
        img.paste(tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)), (0, y, W, y + 1))
    d = ImageDraw.Draw(img)
    d.ellipse([W - 260, 70, W - 70, 260], fill=(255, 222, 89))           # الشمس
    d.ellipse([-180, H - 300, W * 0.62, H + 220], fill=(96, 176, 102))   # تل أيسر
    d.ellipse([W * 0.38, H - 260, W + 180, H + 240], fill=(72, 153, 88)) # تل أيمن
    d.ellipse([int(W * 0.44), int(H * 0.55), int(W * 0.60), int(H * 0.78)], fill=(168, 104, 58))  # جسم الأرنب
    d.ellipse([int(W * 0.455), int(H * 0.42), int(W * 0.585), int(H * 0.60)], fill=(190, 130, 75))  # رأس
    d.ellipse([int(W * 0.475), int(H * 0.34), int(W * 0.505), int(H * 0.46)], fill=(190, 130, 75))  # أذن
    d.ellipse([int(W * 0.53), int(H * 0.34), int(W * 0.56), int(H * 0.46)], fill=(190, 130, 75))    # أذن
    d.text((48, 48), f"p.{page_no}", fill=(30, 60, 90))
    img.save(path)


def generate_images(story: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    use_mock = config.FAKE_LLM or not os.getenv("OPENAI_API_KEY")
    client = None
    if not use_mock:
        from openai import OpenAI
        client = OpenAI()
    for i, page in enumerate(story["pages"], 1):
        out = out_dir / f"p{i}.png"
        if use_mock:
            _mock_image(out, i, story["title"])
        else:
            prompt = (f"Children's book illustration, {story['style']}. "
                      f"Characters (keep identical every page): {story['character_sheet']}. "
                      f"Scene: {page['image_prompt']}. No text, no letters in the image.")
            r = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1024")
            out.write_bytes(base64.b64decode(r.data[0].b64_json))
        paths.append(str(out))
    return paths


# ---------------- بناء الـ PDF ----------------

def build_pdf(story: dict, img_paths, out_pdf: Path):
    import arabic_reshaper
    from bidi.algorithm import get_display
    from reportlab.lib.units import inch
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    language = config.LANGUAGE
    font = "Helvetica"
    if language == "ar" and config.ARABIC_FONT.exists():
        pdfmetrics.registerFont(TTFont("AR", str(config.ARABIC_FONT)))
        font = "AR"

    def shape(t):
        return get_display(arabic_reshaper.reshape(t)) if language == "ar" else t

    S = config.PAGE_SIZE_IN * inch
    c = canvas.Canvas(str(out_pdf), pagesize=(S, S))

    def text_block(txt, size, y_top):
        y = y_top
        for ln in simpleSplit(txt, font, size, S - 1.5 * inch):
            if language == "ar":
                c.drawRightString(S - 0.75 * inch, y, shape(ln))
            else:
                c.drawString(0.75 * inch, y, ln)
            y -= size * 1.5

    c.setFont(font, 34)
    c.drawCentredString(S / 2, S / 2, shape(story["title"]))
    c.showPage()
    for p, img in zip(story["pages"], img_paths):
        c.drawImage(img, 0.5 * inch, 2.2 * inch, S - inch, S - 2.7 * inch, preserveAspectRatio=True)
        c.setFont(font, 20)
        text_block(p["text"], 20, 1.6 * inch)
        c.showPage()
    c.save()
    return str(out_pdf)


# ---------------- النشر على Etsy ----------------

def etsy_create_draft(meta: dict, pdf_path: str, cover_path: str, price: float = 4.99):
    """ينشئ مسودة فقط. يعيد listing_id. بدون مفاتيح يرجع معرفاً تجريبياً."""
    key = os.getenv("ETSY_API_KEY")
    token = os.getenv("ETSY_ACCESS_TOKEN")
    shop = os.getenv("ETSY_SHOP_ID")
    if config.FAKE_LLM or not (key and token and shop):
        slug_seed = re.sub(r"\W+", "", str(meta.get("title", "x")))[:24]
        return f"MOCK-{abs(hash(slug_seed)) % 10**9:09d}", True   # (id, is_mock)

    B = "https://openapi.etsy.com/v3/application"
    headers = {"x-api-key": key, "Authorization": f"Bearer {token}"}
    data = {"quantity": 999, "title": meta["title"][:140], "description": meta["description"],
            "price": price, "who_made": "i_did", "when_made": "made_to_order",
            "taxonomy_id": 0, "type": "download",
            "tags": ",".join(meta.get("tags", [])[:13]), "is_supply": False}
    r = requests.post(f"{B}/shops/{shop}/listings", headers=headers, data=data, timeout=60)
    r.raise_for_status()
    lid = r.json()["listing_id"]
    with open(pdf_path, "rb") as f:
        requests.post(f"{B}/shops/{shop}/listings/{lid}/files", headers=headers,
                      files={"file": f}, data={"name": os.path.basename(pdf_path)},
                      timeout=120).raise_for_status()
    with open(cover_path, "rb") as f:
        requests.post(f"{B}/shops/{shop}/listings/{lid}/images", headers=headers,
                      files={"image": f}, timeout=120).raise_for_status()
    return str(lid), False
