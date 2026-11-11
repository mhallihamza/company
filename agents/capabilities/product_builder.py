"""Product builder — approved Product Brief → full English book/activity content.

The output is a story.json-compatible dict so the existing
media → pdf → qa pipeline can process it unchanged.

Hard rules:
  * English, age-3-to-5 vocabulary
  * Original content — never copied from competitor books
  * No invented marketplace figures
"""
from __future__ import annotations
import json
import os

from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import regex_json
from agents.llm import get_chat_model

PAGES_BY_TYPE = {
    "coloring_book": 24,
    "drawing_workbook": 24,
    "painting_workbook": 24,
    "activity_workbook": 32,
    "tracing_workbook": 32,
    "alphabet_workbook": 32,
    "matching_activity": 24,
    "maze_book": 24,
    "educational_bundle": 42,
}


def build_content_prompt(brief: dict) -> str:
    spec = {
        "coloring_book": ("Black-and-white line art for children ages 3-5. "
                          "Thick, simple outlines. One subject per page. "
                          "No numbers or letters unless child-friendly and intentional."),
        "drawing_workbook": ("Step-by-step drawing instructions for ages 3-5. "
                             "Show a finished model and guided dotted outlines. "
                             "Few simple shapes. Short encouraging prompts."),
        "painting_workbook": ("Painting-friendly prompts for ages 3-5. "
                              "Simple shapes, color suggestions, one task per page. "
                              "No complex techniques."),
        "activity_workbook": ("Mixed activities for ages 3-5: tracing, matching, counting, "
                              "mazes. One task + one image prompt per page. "
                              "Child-safe, inclusive language."),
        "tracing_workbook": ("Handwriting-style tracing for ages 3-5. "
                             "Dotted curve guides, letter families (A-M, N-Z), one group per page. "
                             "Uppercase and lowercase."),
        "alphabet_workbook": ("Alphabet recognition for ages 3-5. "
                              "One letter group per page, picture + word pair, "
                              "tracing and circle-the-letter activity per page."),
        "matching_activity": ("Find-the-pair for ages 3-5: shapes, animals, letters, fruits, vehicles. "
                              "Simple matching grid, no reading required."),
        "maze_book": ("Mazes for ages 3-5: increasing difficulty, "
                      "simple walls, start/finish clearly marked, "
                      "an themed character guide. No text-heavy instructions."),
        "educational_bundle": ("Mixed mini-packs for ages 3-5: ABC tracing, counting, shapes, matching, mazes — "
                               "each mini-pack is self-contained with its own instructions page."),
    }
    desc = spec.get(brief.get("product_type"), spec["coloring_book"])
    keywords = ", ".join(brief.get("keywords", []))
    return (
        f"[ROLE:content_builder]\nYou are a children's product content writer for children ages 3-5. "
        f"Create a complete {desc}\n"
        f"RETURN ONLY this JSON shape (no prose, no markdown):\n"
        f'{{"title": str, "character_sheet": str, "style": str, '
        f'"pages": [{{"text": str (1-3 short sentences, warm, age-appropriate), '
        f'"image_prompt": str (specific, colorful, simple line art for coloring/drawing)}}] }}\n'
        f"Inside pages, cover page 0..N must match: total {brief.get('page_count', 24)} pages. "
        f"Page 0 is the cover (simple, bold, child-friendly). "
        f"Character_sheet must define ONE reusable character consistent across all pages. "
        f"Style must request black-and-white line art when product_type mentions coloring/drawing/tracing. "
        f"Keep ALL text under 4 words when it appears inside images (put any longer text on its own page).\n"
        f"SEED KEYWORDS: {keywords}\n"
        f"NICHE: {brief.get('niche', 'drawing')}\n"
        f"PAGE_COUNT: {brief.get('page_count', 24)}")


def build_product(brief: dict) -> dict:
    """Generate complete product content from an approved Product Brief. Raises on failure."""
    model = get_chat_model(temperature=0.6, max_tokens=3000)
    sys_prompt = build_content_prompt(brief)
    raw = model.invoke([SystemMessage(content=sys_prompt),
                        HumanMessage(content="Write the book now")]).content
    parsed = regex_json(str(raw))

    # normalize to the story shape
    pages = parsed.get("pages") or []
    # pad/truncate to the target page_count
    target = brief.get("page_count") or 24
    if len(pages) > target:
        pages = pages[:target]
    elif len(pages) < target:
        pages = list(pages) + [{"text": "Keep going!", "image_prompt": "happy child finishing the page"}
                               for _ in range(target - len(pages))]

    if not parsed.get("title"):
        parsed["title"] = brief.get("title") or "Untitled"
    if not parsed.get("character_sheet"):
        parsed["character_sheet"] = "friendly cartoon child"
    if not parsed.get("style"):
        parsed["style"] = "black and white line art with thick outlines"

    parsed["slug"] = None   # caller sets the slug
    parsed["etsy"] = {
        "title": (brief.get("title") + " — PDF for Kids")[:140],
        "description": _etsy_description(brief),
        "tags": (brief.get("keywords") or ["kids book"])[:13],
    }
    parsed["product_type"] = brief.get("product_type")
    parsed["marketplace"] = brief.get("marketplace")
    parsed["brief"] = brief

    pages = [{"text": str(p.get("text") or "").strip(),
              "image_prompt": str(p.get("image_prompt") or p.get("prompt") or "child drawing").strip()}
             for p in pages]

    parsed["pages"] = pages
    return parsed


def _etsy_description(brief: dict) -> str:
    desc = str(brief.get("description") or "An engaging children product.")
    return (desc
            + f" Ages {brief.get('target_age', '3-5')}. "
            + "Print-it-easy PDF, instant download after purchase. "
            + "Perfect for parents, grandparents, teachers, and homeschoolers.")
