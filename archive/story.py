from config import LANGUAGE, AGE_RANGE, PAGES
from llm import ask_json

def make_story(idea: str):
    lang = "Modern Standard Arabic (simple, fully vowel-free but clear)" if LANGUAGE == "ar" else "English"
    return ask_json(f"""Write a picture book for children aged {AGE_RANGE}, in {lang}.
Idea: {idea}
Exactly {PAGES} pages, 1-3 short sentences per page, positive values, no scary content.
JSON schema:
{{"title": str,
  "character_sheet": "very detailed fixed visual description of every character (colors, clothes, shape)",
  "style": "one fixed art style sentence, e.g. soft watercolor, warm colors",
  "pages": [{{"text": str, "image_prompt": "scene description only, no text in image"}}],
  "etsy": {{"title": str, "description": str, "tags": [13 short tags]}}}}""", max_tokens=6000)
