"""design — draft render table: waits for an image provider hookup (IMAGE_PROVIDER). No real generation yet."""
from __future__ import annotations

from agents.common import HQState
from agents.registry import AgentSpec, DepartmentSpec, register


def run(task: str = "", task_id: int | None = None, workspace: str = "default") -> dict:
    return {
        "ok": False,
        "task_id": task_id,
        "error": ("Design department needs an image provider hook (IMAGE_PROVIDER): "
                  "set IMAGE_PROVIDER=openai or paddle, then add your keys to .env."),
    }


register(DepartmentSpec(
    key="design", sector="design",
    title_ar="Design Studio", title_en="Design Studio",
    description_ar="Connects an external image provider, then generates covers/art — needs IMAGE_PROVIDER.",
    description_en='External image provider hook (unwired until IMAGE_PROVIDER set)',
    capabilities=["cover_design", "interior_render", "thumbnails"],
    allowed_tools=["image_provider"],
    approval_policy="content_gate",
    run=run, budget_limit_usd=20.0,
    enabled=True,
    agents=[
        AgentSpec("designer", "art direction + cover/interior render (unwired)", "reasoning", ["image_generation"]),
    ],
))
