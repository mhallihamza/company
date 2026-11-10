"""Reports — list + download PDF/MD from storage."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.app.auth import require_founder
from backend.app.services import store as svc

router = APIRouter(tags=["reports"], dependencies=[Depends(require_founder)])


@router.get("/reports")
def list_reports(limit: int = 60):
    return svc.list_reports(limit=limit)


@router.get("/reports/{report_id}/download")
def download_report(report_id: int):
    rows = svc.list_reports(limit=10000)
    match = next((r for r in rows if r["report_id"] == report_id), None)
    if not match:
        raise HTTPException(404, "no report with this id")
    path = Path((match.get("path") or ""))
    if not path.exists():
        raise HTTPException(410, "report path no longer exists")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")
