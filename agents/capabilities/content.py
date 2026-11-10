"""Story writing and validation — the model reads, Python verifies."""
from __future__ import annotations
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState, regex_json
from agents.llm import get_chat_model


def validate_story(story: Any, pages: int) -> dict[str, Any]:
    if not isinstance(story, dict):
        raise ValueError("القصة ليست كائناً JSON")
    for key in ("title", "character_sheet", "style", "pages", "etsy"):
        if key not in story:
            raise ValueError(f"الحقل الإلزامي مفقود: {key}")
    for key, value in (("title", str), ("character_sheet", str), ("style", str)):
        if not isinstance(story[key], value):
            raise ValueError(f"{key} يجب أن تكون {value.__name__}")
    if not isinstance(story["pages"], list) or len(story["pages"]) != pages:
        raise ValueError(f"عدد الصفحات يجب أن يكون {pages} — الموجود {len(story.get('pages', []))}")
    story["pages"] = [_page(i, p) for i, p in enumerate(story["pages"])]
    etsy = story["etsy"] if isinstance(story["etsy"], dict) else {}
    etsy.setdefault("title", story["title"])
    etsy["title"] = str(etsy["title"])[:140]
    etsy.setdefault("description", "")
    tags = [str(t)[:35] for t in (etsy.get("tags") or [])][:13]
    etsy["tags"] = tags or ["قصص أطفال"]
    story["etsy"] = etsy
    return story


def _page(i: int, page: Any) -> dict[str, str]:
    if not isinstance(page, dict):
        raise ValueError(f"الصفحة {i+1} ليست كائناً")
    text = str(page.get("text") or "").strip()
    prompt = str(page.get("image_prompt") or "").strip()
    if not text or not prompt:
        raise ValueError(f"الصفحة {i+1} ينقصها نص أو وصف رسم")
    return {"text": text, "image_prompt": prompt}


def write_story(idea: str, language: str = "ar", pages: int = 12) -> dict[str, Any]:
    from agents.localization import get_language_profile, get_story_prompt

    lang = (language or "ar").strip().lower()
    profile = get_language_profile(lang)   # fail fast on unknown code — never guess
    model = get_chat_model(temperature=0.7, max_tokens=3000)
    attempts = 2
    last_error: Exception | None = None
    for attempt in range(attempts):
        sys = get_story_prompt(lang, idea, pages)
        try:
            raw = model.invoke([SystemMessage(content=sys),
                                HumanMessage(content=profile.story_human)]).content
            story = regex_json(str(raw))
            return validate_story(story, pages)
        except Exception as e:  # noqa: BLE001
            last_error = e
            sys += f"\nالمرة الأخيرة فشلت لأن: {e}. أخرج JSON صالحاً ONLY.\n"
    raise ValueError(f"فشل توليد قصة صالحة بعد {attempts} محاولة: {last_error}")

from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="content_generation",
    title_en="Content Generation", title_ar="توليد المحتوى",
    description_en="Arabic story JSON generation + validation (Python checks the model's work).",
    description_ar="توليد قصة JSON بالعربية + تحقق صارم من الفحص المنطقي لـ Python.",
    used_by=["books.content", "books.market", "marketing", "intelligence"], deterministic=False,
))
