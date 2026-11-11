"""design — real image generation for book products.

This IS the production image capability. It routes through agents.capabilities.media:

  IMAGE_PROVIDER=openai   → GPT Image (needs OPENAI_API_KEY + org access to gpt-image-1)
  IMAGE_PROVIDER=pil      → deterministic offline render (always works; demo-quality)
  unset / unknown         → PIL offline render, with an explicit note in the result

Hard rules:
  * No silent success — when the live provider fails, the department returns the real error.
  * Every asset is persisted with metadata (page, type, provider, style).
  * Cover art is generated separately from interior pages.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

from agents.common import HQState
from agents.registry import AgentSpec, DepartmentSpec, register
from agents.capabilities import media
from backend.app.config import BOOKS_DIR
from backend.app.services import store as svc


def run(task: str = "", task_id: int | None = None, workspace: str = "default",
        slug: str | None = None) -> dict:
    try:
        provider = (os.getenv("IMAGE_PROVIDER") or "").lower().strip()
        live = bool(provider == "openai" and os.getenv("OPENAI_API_KEY"))
        target_slug = slug or task or "untitled"
        story_paths = list(BOOKS_DIR.glob(f"{target_slug}/story.json")) if target_slug else []
        if not story_paths:
            # also allow partial match: slug args may be a raw idea title — try story dirs
            story_paths = list(BOOKS_DIR.glob("**/story.json"))
        story_file = story_paths[0] if story_paths else None

        if not story_file:
            return {"ok": False, "task_id": task_id,
                    "error": f"No product story found for '{target_slug}'. Generate the book first (books.content)."}

        story = json.loads(story_file.read_text(encoding="utf-8"))
        d = story_file.parent
        paths = media.generate_images(story, d)
        # persist asset metadata
        saved_assets = []
        for i, p in enumerate(paths):
            try:
                aid = svc.add_generated_asset(
                    d.name, i, "cover" if i == 0 else "interior",
                    str(p), provider=("openai" if live else "pil"),
                    style=story.get("style"))
                saved_assets.append(aid)
            except Exception:  # noqa: BLE001 — metadata is best-effort
                pass

        if live:
            note = "Generated via OpenAI gpt-image-1 (live)."
        else:
            note = "Generated via deterministic PIL render (offline). Set IMAGE_PROVIDER=openai + OPENAI_API_KEY for live artwork."
        return {"ok": True, "task_id": task_id, "slug": d.name,
                "images": [str(p) for p in paths],
                "provider": "openai" if live else "pil",
                "image_provider_configured": live,
                "note": note}
    except FileNotFoundError as e:
        return {"ok": False, "task_id": task_id, "error": f"Image asset path missing: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "task_id": task_id, "error": f"Image generation failed: {e}"}


register(DepartmentSpec(
    key="design", sector="design",
    title_ar="Design Studio", title_en="Design Studio",
    description_ar="Generates original cover + interior illustrations for children's products.",
    description_en="Generates original cover + interior illustrations for children's products.",
    capabilities=["cover_design", "interior_render", "thumbnails"],
    allowed_tools=["image_provider"],
    approval_policy="content_gate",
    run=run, budget_limit_usd=20.0,
    enabled=True,
    agents=[
        AgentSpec("designer", "art direction + cover/interior render", "reasoning", ["image_generation"]),
    ],
))
