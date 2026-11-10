"""Language/profile localization — the ONLY supported language adapters (en, fr).

Provides, per language:
  story writer instructions
  font reference resolution (amiri / dejavu) with explicit search paths
  text direction
  QA rule strings consumed by QA departments

Anything outside en/fr → UnsupportedLanguage (fail fast; never guess).
"""
from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AMIRI = ROOT / "fonts" / "Amiri-Regular.ttf"


class UnsupportedLanguage(ValueError):
    """Raised when a language code matches no adapter — never silently default."""


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
    """Resolve a font reference. amiri → repo font (Latin coverage too); dejavu → OS font."""
    ref = (font_ref or "").strip().lower()
    if ref == "font.amiri":
        if AMIRI.exists():
            return AMIRI
        raise FileNotFoundError(f"font.amiri expected at {AMIRI} — file missing")
    if ref == "font.dejavu":
        for candidate in _dejavu_candidates():
            if candidate.exists():
                return candidate
        # Amiri includes full Latin coverage — documented fallback for Latin scripts
        if AMIRI.exists():
            return AMIRI
        raise FileNotFoundError(
            "font.dejavu not found — looked in: " + ", ".join(str(p) for p in _dejavu_candidates())
            + f"; no Amiri fallback at {AMIRI} either")
    # last resort honest fallback: the only font we ship — say so, don't fake it
    if AMIRI.exists():
        return AMIRI
    raise FileNotFoundError(f"unknown font_ref '{ref}' and no fallback font present at {AMIRI}")


# ---------- QA rules ----------
QA_RULES: dict[str, tuple[str, ...]] = {
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
    qa_ruleset_ref: str             # 'qa.en' | 'qa.fr'
    qa_rules: tuple[str, ...]
    etsy_locale: str                # e.g. 'en-US', 'fr-FR'


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


def list_supported() -> list[str]:
    return sorted(_STORY)
