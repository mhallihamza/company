"""Language/profile localization — the ONLY supported language adapters (en, fr, ar).

Provides, per language:
  story writer instructions (en / fr / ar)
  font reference resolution (amiri / dejavu) with explicit search paths
  text direction (rtl for ar/he, else ltr)
  QA rule strings consumed by QA departments

Anything outside en/fr/ar → UnsupportedLanguage (fail fast; never guess).
"""
from __future__ import annotations
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AMIRI = ROOT / "fonts" / "Amiri-Regular.ttf"


class UnsupportedLanguage(ValueError):
    """Raised when a language code matches no adapter — never silently default to Arabic."""


# ---------- fonts ----------
def _dejavu_candidates() -> list[Path]:
    if sys.platform.startswith("win"):
        return [Path(r"C:\Windows\Fonts\DejaVuSerif.ttf"),
                Path(r"C:\Windows\Fonts\DejaVu Serif.ttf")]
    if sys.platform == "darwin":
        return [Path("/Library/Fonts/DejaVuSerif.ttf"),
                Path("/System/Library/Fonts/Supplemental/DejaVuSerif.ttf")]
    return [Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSerif.ttf")]


def font_path_for(font_ref: str) -> Path:
    """Resolve a font reference. amiri → repo font; dejavu → OS font (explicit search)."""
    ref = (font_ref or "").strip().lower()
    if ref == "font.amiri":
        if AMIRI.exists():
            return AMIRI
        raise FileNotFoundError(f"font.amiri expected at {AMIRI} — file missing")
    if ref == "font.dejavu":
        for candidate in _dejavu_candidates():
            if candidate.exists():
                return candidate
        # Amiri includes full Latin coverage (upper/lower case, punctuation, digits)
        if AMIRI.exists():
            return AMIRI   # documented fallback — Latin books typeset in Amiri
        raise FileNotFoundError(
            "font.dejavu not found — looked in: " + ", ".join(str(p) for p in _dejavu_candidates())
            + f"; no Amiri fallback at {AMIRI} either")
    # last resort honest fallback: the only font we ship — say so, don't fake it
    if AMIRI.exists():
        return AMIRI
    raise FileNotFoundError(f"unknown font_ref '{ref}' and no fallback font present at {AMIRI}")


# ---------- QA rules ----------
QA_RULES: dict[str, tuple[str, ...]] = {
    "ar": (
        "qa.ar.1",  # title must contain Arabic-script characters
        "qa.ar.2",  # no unescaped Latin words inside Arabic story text (proper terms excepted)
        "qa.ar.3",  # text direction is rtl
        "qa.ar.4",  # Amiri font required before PDF build
    ),
    "en": (
        "qa.en.1",  # plain English prose, no untranslated words from other scripts
        "qa.en.2",  # ltr direction
        "qa.en.3",  # DejaVu Serif or Latin-compatible font required before PDF build
    ),
    "fr": (
        "qa.fr.1",  # French prose with proper accents (é è ç ê à ô î û)
        "qa.fr.2",  # ltr direction
        "qa.fr.3",  # no English words in French story text
        "qa.fr.4",  # DejaVu Serif or Latin-compatible font required before PDF build
    ),
}


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    name: str
    story_system: str               # system instructions for the story writer
    story_human: str                # user turn for the story writer
    font_ref: str                   # resolved by font_path_for()
    text_direction: str             # rtl | ltr
    qa_ruleset_ref: str             # 'qa.ar' | 'qa.en' | 'qa.fr'
    qa_rules: tuple[str, ...]
    etsy_locale: str                # e.g. 'en-US', 'fr-FR', 'ar'


_STORY = {
    "en": LanguageProfile(
        code="en", name="English",
        story_system=("You are a warm English children's-story writer. "
                      "Short English sentences for ages 3-6. "
                      "Return ONLY valid JSON: "
                      '{"title": str, "character_sheet": str, "style": str, '
                      '"pages": [{"text": str, "image_prompt": str}], '
                      '"etsy": {"title": str, "description": str, "tags": [str]} }'),
        story_human="Write the story",
        font_ref="font.dejavu", text_direction="ltr",
        qa_ruleset_ref="qa.en", qa_rules=QA_RULES["en"], etsy_locale="en-US"),
    "fr": LanguageProfile(
        code="fr", name="Français",
        story_system=("Tu es un écrivain chaleureux d'histoires pour enfants en français. "
                      "Des phrases françaises courtes pour les 3-6 ans, avec les accents. "
                      "Retourne UNIQUEMENT du JSON valide : "
                      '{"title": str, "character_sheet": str, "style": str, '
                      '"pages": [{"text": str, "image_prompt": str}], '
                      '"etsy": {"title": str, "description": str, "tags": [str]} }'),
        story_human="Écris l'histoire",
        font_ref="font.dejavu", text_direction="ltr",
        qa_ruleset_ref="qa.fr", qa_rules=QA_RULES["fr"], etsy_locale="fr-FR"),
    "ar": LanguageProfile(
        code="ar", name="Arabic",
        story_system=("أنت كاتب قصص أطفال دافئ بالعربية. جمل عربية قصيرة للأطفال من 3-6 سنوات. "
                      "أعد فقط JSON صالح: "
                      '{"title": str, "character_sheet": str, "style": str, '
                      '"pages": [{"text": str, "image_prompt": str}], '
                      '"etsy": {"title": str, "description": str, "tags": [str]} }'),
        story_human="اكتب القصة",
        font_ref="font.amiri", text_direction="rtl",
        qa_ruleset_ref="qa.ar", qa_rules=QA_RULES["ar"], etsy_locale="ar"),
}


def get_language_profile(code: str) -> LanguageProfile:
    c = (code or "").strip().lower()
    if c not in _STORY:
        raise UnsupportedLanguage(f"unsupported language '{code}' — supported: {sorted(_STORY)}")
    return _STORY[c]


def get_story_prompt(code: str, idea: str, pages: int) -> str:
    profile = get_language_profile(code)
    return ("[ROLE:story_writer]\n" + profile.story_system + "\n"
            f"Exactly {pages} pages.\n"
            f"IDEA: {idea.strip()[:180]}\nPAGES: {pages}\n")


def has_arabic_script(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def list_supported() -> list[str]:
    return sorted(_STORY)
