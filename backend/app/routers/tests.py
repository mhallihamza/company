"""product_tests — نتائج حقيقية بعد 2-4 أسابيع اختبر بها الفرصة بصراحة."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from backend.app.auth import require_founder
from backend.app.db import get_store
from backend.app.services import store as svc

router = APIRouter(tags=["tests"], dependencies=[Depends(require_founder)])


class TestIn(BaseModel):
    opportunity_id: int = Field(..., ge=1)
    channel: str
    views: int = Field(0, ge=0)
    favorites: int = Field(0, ge=0)
    sales: int = Field(0, ge=0)
    notes: str = Field("", max_length=1000)


@router.post("/tests")
def log_test(body: TestIn):
    """Log a 2–4 week test outcome against an opportunity — no extrapolation, just raw numbers."""
    rows = svc.q("SELECT opportunity_id FROM opportunities WHERE opportunity_id=?",
                 (body.opportunity_id,))
    if not rows:
        raise HTTPException(404, f"no opportunity #{body.opportunity_id}")
    sql = ("INSERT INTO product_tests (opportunity_id, channel, views, favorites, sales, "
           "test_start, notes, workspace_id) "
           "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP,?,?) RETURNING test_id")
    s = get_store()
    sql = sql.replace("?", "%s" if s.kind == "pg" else "?")
    with s._cur() as cur:  # noqa: SLF001
        cur.execute(sql, (body.opportunity_id, body.channel, body.views,
                          body.favorites, body.sales, body.notes[:500], "default"))
        row = cur.fetchone()
        test_id = int(row["test_id"] if isinstance(row, dict) else row[0])
    return {"ok": True, "test_id": test_id}

@router.get("/tests")
def list_tests(opportunity_id: Optional[int] = None, channel: Optional[str] = None, limit: int = 60):
    """List recorded tests; grouped by channel so the founder can eyeball performance."""
    rows = svc.q("SELECT * FROM product_tests ORDER BY test_id DESC LIMIT 200")
    if opportunity_id is not None:
        rows = [r for r in rows if r.get("opportunity_id") == opportunity_id]
    if channel:
        rows = [r for r in rows if r.get("channel") == channel]
    return rows


@router.get("/tests/correlation")
def correlation_view():
    """Tiny stand-in for a correlation report — not statistics; raw rows grouped for manual audit."""
    rows = svc.q("SELECT * FROM product_tests ORDER BY test_id DESC LIMIT 500")
    opp_map: dict[int, int] = {}
    for r in rows:
        opp_map[r["opportunity_id"]] = opp_map.get(r["opportunity_id"], 0) + int(r.get("sales", 0))
    return {"opportunity_sales": opp_map,
            "by_channel": _group_by_channel(rows)}


def _group_by_channel(rows: list[dict]) -> dict[str, dict]:
    by: dict[str, dict] = {}
    for r in rows:
        ch = r.get("channel") or "unknown"
        grp = by.setdefault(ch, {"tests": 0, "sales": 0, "favorites": 0, "views": 0})
        grp["tests"] += 1
        grp["sales"] += int(r.get("sales", 0) or 0)
        grp["favorites"] += int(r.get("favorites", 0) or 0)
        grp["views"] += int(r.get("views", 0) or 0)
    return by
