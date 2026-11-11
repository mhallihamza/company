"""Books — story, build, QA and publishing behind approvals."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agents.departments.books import content, publishing
from agents.departments.qa import checker as qa_checker
from backend.app.auth import require_founder
from backend.app.config import BOOKS_DIR
from backend.app.services import store as svc

router = APIRouter(tags=["books"], dependencies=[Depends(require_founder)])


class CreateStoryIn(BaseModel):
    idea: str = Field(..., min_length=3, max_length=500)


class BuildIn(BaseModel):
    slug: str


@router.get("/books/{slug}/pdf")
def download_book_pdf(slug: str):
    """Stream the book PDF to the founder (cross-check runs in-session)."""
    product = svc.get_product(slug)
    if not product:
        raise HTTPException(404, f"No product named «{slug}»")
    if not product.get("pdf_path"):
        raise HTTPException(422, "No PDF built for this book — build it first")
    path = Path(product["pdf_path"])
    if not path.exists():
        raise HTTPException(410, "PDF no longer exists on disk")
    return FileResponse(path, filename=f"{slug}.pdf", media_type="application/pdf")


@router.get("/books/{slug}/interior_kdp")
def download_kdp_interior(slug: str):
    """Stream the KDP print-ready interior PDF (6x9)."""
    product = svc.get_product(slug)
    if not product:
        raise HTTPException(404, f"No product named «{slug}»")
    path = BOOKS_DIR / slug / "interior_kdp.pdf"
    if not path.exists():
        raise HTTPException(410, "KDP interior PDF no longer exists on disk — rebuild the book")
    return FileResponse(path, filename=f"{slug}-kdp.pdf", media_type="application/pdf")


@router.get("/books/{slug}/asset/{asset_name}")
def download_asset(slug: str, asset_name: str):
    """Stream a generated asset (PNG/JPG) for the given product."""
    product = svc.get_product(slug)
    if not product:
        raise HTTPException(404, f"No product named «{slug}»")
    # whitelist filename — no path traversal
    if any(c in asset_name for c in "/\\.."):
        raise HTTPException(400, "invalid asset name")
    path = BOOKS_DIR / slug / asset_name
    if not path.exists():
        raise HTTPException(410, f"asset {asset_name!r} not found")
    return FileResponse(path)


class PublishRequestIn(BaseModel):
    slug: str
    note: str = ""


class SetTargetsIn(BaseModel):
    platforms: list[str]


_KNOWN_PLATFORMS = [
    {"id": "etsy", "name": "Etsy (digital download PDF)",
     "how": "PDF download listing — request your Etsy shop approval after sign-off",
     "points": ["Low risk · no shipping", "Saves Arabic/Arabic-English metadata outside KDP restrictions"]},
    {"id": "kdp_paperback", "name": "Amazon KDP (paperback)",
     "how": "Print-on-demand paperback — manual upload to KDP after your sign-off",
     "points": ["Physical book on Amazon", "Requires print-ready PDF"]},
    {"id": "kdp_ebook", "name": "Amazon KDP (eBook/Kindle)",
     "how": "Kindle edition — side-by-side with paperback",
     "points": ["Instant delivery, royalty 35–70%", "Easy AR/EN bundles"]},
    {"id": "gumroad", "name": "Gumroad (direct download)",
     "how": "Direct-to-founder download — low fees, no marketplace rules",
     "points": ["Fastest path to revenue", "Your customer list"]},
    {"id": "shopify", "name": "Shopify (mockup/store)",
     "how": "Your own store with PDF delivery app",
     "points": ["Brand-controlled", "Requires storefront setup"]},
]


@router.post("/books")
def create_book(body: CreateStoryIn):
    task_id = svc.create_task("create_story", "books.content",
                              ref=body.idea[:100], input_text=body.idea)
    out = content.run(idea=body.idea, task_id=task_id, stop_after="story")
    svc.finish_task(task_id, "success" if out.get("ok") else "failed",
                    (out.get("summary") or out.get("error") or "")[:400])
    if not out.get("ok"):
        raise HTTPException(422, out.get("error") or "failed to write the story")
    return out


@router.get("/books")
def list_books():
    return svc.list_products()


@router.get("/books/{slug}")
def get_book(slug: str):
    product = svc.get_product(slug)
    story_file = BOOKS_DIR / slug / "story.json"
    story = None
    if story_file.exists():
        story = json.loads(story_file.read_text(encoding="utf-8"))
    return {"product": product, "story": story}


@router.put("/books/{slug}/story")
def edit_story(slug: str, story: dict):
    story_file = BOOKS_DIR / slug / "story.json"
    if not story_file.exists():
        raise HTTPException(404, f"no story for {slug}")
    story_file.write_text(json.dumps(story, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return {"ok": True, "path": str(story_file)}


@router.post("/books/{slug}/build")
def build_book(slug: str):
    task_id = svc.create_task("build_book", "books.content", ref=slug)
    out = content.build_existing(slug)
    out["task_id"] = task_id
    svc.finish_task(task_id, "success" if out.get("ok") else "failed",
                    (out.get("summary") or out.get("error") or "")[:400])
    if not out.get("ok"):
        raise HTTPException(422, out.get("error") or "failed to build the book")
    return out


@router.post("/qa/{slug}")
def qa_report(slug: str):
    out = qa_checker.run(slug)
    return out


@router.get("/books/{slug}/assets")
def list_assets(slug: str):
    return svc.list_generated_assets(slug)


@router.get("/books/{slug}/qa")
def qa_list(slug: str):
    return svc.list_qa_reports(slug)


@router.get("/books/{slug}/brief")
def brief(slug: str):
    from agents.capabilities.product_brief import product_types
    rows = svc.q("SELECT * FROM product_briefs ORDER BY brief_id DESC LIMIT 20")
    return {"types": product_types(), "recent_briefs": rows}


@router.post("/books/{slug}/publish-request")
def publish_request(slug: str, body: PublishRequestIn | None = None):
    product = svc.get_product(slug)
    if not product:
        raise HTTPException(404, f"no product '{slug}'")
    if not product.get("pdf_path") or not Path(product["pdf_path"]).exists():
        raise HTTPException(422, "no PDF ready — build the book first")
    note = (body.note if body else None) or f"Etsy draft publish request for {slug}"
    aid = svc.create_approval("etsy_publish", slug, note=note)
    svc.audit(None, "human", "request_publish", f"approval={aid} slug={slug}")
    return {"ok": True, "approval_id": aid, "status": "pending"}


@router.get("/platforms")
def list_platforms():
    return _KNOWN_PLATFORMS


@router.post("/books/{slug}/targets")
def set_targets(slug: str, body: SetTargetsIn):
    product = svc.get_product(slug)
    if not product:
        raise HTTPException(404, f"no product '{slug}'")
    known = {p["id"] for p in _KNOWN_PLATFORMS}
    targets = [t for t in body.platforms if t in known]
    if not targets:
        raise HTTPException(422, f"no valid platform IDs. Known: {sorted(known)}")
    svc.set_product_targets(slug, targets)
    return {"ok": True, "slug": slug, "targets": targets}
