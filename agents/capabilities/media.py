"""Image generation — OpenAI GPT-Image when IMAGE_PROVIDER=openai, PIL fallback otherwise.

Legacy image.py had the provider hook but no working fallback; here both live:
deterministic PIL render keeps the demo/tests running, OpenAI does real artwork
when you wire OPENAI_API_KEY.
"""
from __future__ import annotations
import base64
import hashlib
import os
from pathlib import Path

from PIL import Image, ImageDraw


def generate_images(story: dict, out_dir: Path) -> list[str]:
    provider = os.getenv("IMAGE_PROVIDER", "").lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    if provider == "openai" and os.getenv("OPENAI_API_KEY"):
        return _generate_openai(story, out_dir)
    return _generate_pil(story, out_dir)


def _generate_openai(story: dict, out_dir: Path) -> list[str]:
    from openai import OpenAI
    client = OpenAI()
    style = story.get("style", "soft watercolor children's book illustration")
    chars = story.get("character_sheet", "")
    paths = []

    def _render(prompt: str, path: Path) -> str:
        full = (f"Children's book illustration, {style}. "
                f"Characters (keep identical across pages): {chars}. "
                f"Scene: {prompt}. No text, no letters in the image.")
        r = client.images.generate(model="gpt-image-1", prompt=full, size="1024x1024")
        path.write_bytes(base64.b64decode(r.data[0].b64_json))
        return str(path)

    paths.append(_render(f"Cover art for «{story.get('title', 'book')}»",
                         out_dir / "p0_cover.png"))
    for i, page in enumerate(story.get("pages", [])):
        paths.append(_render(page.get("image_prompt", "story scene"),
                             out_dir / f"p{i+1}.png"))
    return paths


def _generate_pil(story: dict, out_dir: Path) -> list[str]:
    seed = int(hashlib.sha256(story.get("title", "").encode()).hexdigest(), 16)
    palette = [
        ("#FFD166", "#06D6A0", "#EF476F"),
        ("#8ECAE6", "#FFB703", "#FB8500"),
        ("#E0AAFF", "#B9FBC0", "#70D6FF"),
    ][seed % 3]

    paths = []
    cover = _scene(out_dir / "p0_cover.png", str(story.get("title", "Untitled")),
                   story.get("character_sheet", ""), palette, seed)
    paths.append(str(cover))
    for i, page in enumerate(story.get("pages", [])):
        img = _scene(out_dir / f"p{i+1}.png", str(page.get("image_prompt", "")),
                     story.get("style", ""), palette, seed + i * 7)
        paths.append(str(img))
    return paths


def _scene(path: Path, text: str, extra: str, palette: tuple, seed: int) -> Path:
    size = 1024
    bg, accent, pop = palette
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    r = 60 + (seed % 140)
    cx = size // 2 + (seed % 160) - 80
    cy = int(size * 0.38)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent)
    draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill="#FFF6E4")
    for ex in (cx - r // 3, cx + r // 3):
        draw.ellipse([ex - 18, cy - 14, ex + 18, cy + 22], fill="#2B2D42")
    draw.arc([cx - 40, cy + 10, cx + 40, cy + 60], 20, 160, fill="#2B2D42", width=6)
    draw.rounded_rectangle([80, int(size * 0.72), size - 80, size - 60], radius=36,
                           outline=pop, width=10, fill="#FFFFFF22")
    img.save(path, "PNG")
    return path


from agents.capabilities import CapabilitySpec, register_capability
register_capability(CapabilitySpec(
    id="image_generation",
    title_en="Image Generation", title_ar="توليد الصور",
    description_en="Character-consistent page art: OpenAI gpt-image-1 when IMAGE_PROVIDER=openai, deterministic PIL render otherwise.",
    description_ar="رسوم صفحات بشخصية ثابتة: OpenAI عندما IMAGE_PROVIDER=openai، وإلا PIL حتمي.",
    used_by=["books.content", "design"], deterministic=False,
))
