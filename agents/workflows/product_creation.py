"""product_creation — builds book candidates (candidate → pdf) without enabling publishing."""
from __future__ import annotations

from agents.departments.books import content
from backend.app.services import store as svc


def run(limit: int = 1) -> dict:
    rows = svc.list_products(limit=100)
    created = []
    for product in rows:
        if product.get("status") != "candidate":
            continue
        title = product.get("title", "")
        out = content.run(idea=title, task_id=None)
        svc.audit(None, "workflow", "product_creation",
                  f"{product['slug']} → ok={out.get('ok')} slug={out.get('slug')}"[:500])
        created.append({"candidate": product["slug"], "ok": out.get("ok"),
                        "summary": out.get("summary"), "slug": out.get("slug")})
        if len(created) >= limit:
            break
    return {"built": created}
