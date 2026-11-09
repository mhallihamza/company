"""design — مسودة جدول رسوم: ينتظر ربط مزود صور (IMAGE_PROVIDER). لا يوجد توليد فعلي بعد."""
from __future__ import annotations

from agents.common import HQState
from agents.registry import AgentSpec, DepartmentSpec, register


def run(task: str = "", task_id: int | None = None, workspace: str = "default") -> dict:
    return {
        "ok": False,
        "task_id": task_id,
        "error": ("قسم التصميم بحاجة لربط مزود صور (IMAGE_PROVIDER): "
                  "اجعل IMAGE_PROVIDER=openai أو paddle، ثم أدخل مفاتيحك في .env."),
    }


register(DepartmentSpec(
    key="design", sector="design",
    title_ar="التصميم والاستوديو الإبداعي", title_en="Design Studio",
    description_ar="يربط مزود صور خارجي ثم يولّد أغلفة والصور — بحاجة إلى IMAGE_PROVIDER",
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
