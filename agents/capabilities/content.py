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
        raise ValueError("Story is not a JSON object")
    for key in ("title", "character_sheet", "style", "pages", "etsy"):
        if key not in story:
            raise ValueError(f"Missing required field: {key}")
    for key, value in (("title", str), ("character_sheet", str), ("style", str)):
        if not isinstance(story[key], value):
            raise ValueError(f"{key} must be {value.__name__}")
    if not isinstance(story["pages"], list):
        raise ValueError("pages must be a list")
    target = pages
    got = len(story["pages"])
    if got > target:
        story["pages"] = list(story["pages"])[:target]
    elif got < target:
        story["pages"] = list(story["pages"]) + [
            {"text": "One more adventure!", "image_prompt": "child smiling, simple watercolor"}] * (target - got)
    story["pages"] = [_page(i, p) for i, p in enumerate(story["pages"])]
    etsy = story["etsy"] if isinstance(story["etsy"], dict) else {}
    etsy.setdefault("title", story["title"])
    etsy["title"] = str(etsy["title"])[:140]
    etsy.setdefault("description", "")
    tags = [str(t)[:35] for t in (etsy.get("tags") or [])][:13]
    etsy["tags"] = tags or ["kids story book"]
    story["etsy"] = etsy
    return story


def _page(i: int, page: Any) -> dict[str, str]:
    if not isinstance(page, dict):
        return {"text": "Keep reading!", "image_prompt": f"children's book illustration for page {i+1}, simple watercolor"}
    text = str(page.get("text") or "").strip()
    prompt = str(page.get("image_prompt") or "").strip()
    if not text:
        text = "Adventure continues..."
    if not prompt:
        prompt = f"Children's book illustration for page {i+1}, soft watercolor, simple shapes"
    return {"text": text, "image_prompt": prompt}


def write_story(idea: str, language: str = "en", pages: int = 12) -> dict[str, Any]:
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
            sys += f"\nRetry reason: {e}. Produce ONLY valid JSON.\n"
    raise ValueError(f"Failed to generate a valid story after {attempts} attempts: {last_error}")

from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="content_generation",
    title_en="Content Generation", title_ar="Content Generation",
    description_en="Arabic story JSON generation + validation (Python checks the model's work).",
    description_ar="English story JSON generation with strict Python validation.",
    used_by=["books.content", "books.market", "marketing", "intelligence"], deterministic=False,
))
