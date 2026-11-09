"""واجهة REST فوق قلب أعمال kidbook — جسر مستقبلي لأي واجهة Next.js.

التشغيل:
    .\\.venv\\Scripts\\uvicorn.exe kidbook.api:app --port 8700

النقاط:
    GET  /health                  الصحة: قاعدة البيانات + النموذج
    GET  /departments             الأقسام المسجلة (سجل الأقسام)
    POST /ceo/run                 {"text": "..."} → CEO يوجّه للقسم الأنسب
    GET  /books                   الكتب
    GET  /opportunities?sector=   الفرص
    GET  /approvals?status=       الموافقات
    POST /approvals/{id}/decide   {"decision": "approve|reject", "note": "..."}
    POST /publish-request         {"slug": "...", "note": "..."} طلب موافقة
    GET  /reports                 آخر التقارير
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from kidbook import engine
from kidbook.db import get_store


class TaskIn(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000, description="المهمة الحرة")


class DecideIn(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    note: str = Field("", max_length=500)


class PublishRequestIn(BaseModel):
    slug: str = Field(..., max_length=100)
    note: str = Field("", max_length=500)


app = FastAPI(title="KidBook AI Business HQ API", version="2.0",
              description="CEO LangGraph API فوق قلب الأعمال")


@app.get("/health")
def health():
    store = get_store()
    from kidbook.llm import mode_label, llm_last_note
    return {"ok": True, "db": store.backend_label, "llm_mode": mode_label(),
            "llm_note": llm_last_note()}


@app.get("/departments")
def departments():
    return [{"key": s.key, "title": s.title, "description": s.description,
             "agents": s.agents, "capabilities": s.capabilities,
             "approval_policy": s.approval_policy, "keywords": s.keywords}
            for s in engine.DOMAIN_REGISTRY.values()]


@app.post("/ceo/run")
def ceo_run(body: TaskIn):
    out = engine.run_task(body.task)
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=out.get("error") or "فشل التنفيذ")
    return out


@app.get("/books")
def books():
    return get_store().list_books()


@app.get("/opportunities")
def opportunities(sector: Optional[str] = None, status: Optional[str] = None,
                  limit: int = 100):
    return get_store().list_opportunities(sector=sector, status=status, limit=limit)


@app.get("/approvals")
def approvals(status: Optional[str] = None, limit: int = 100):
    return get_store().list_approvals(status=status, limit=limit)


@app.post("/publish-request")
def publish_request(body: PublishRequestIn):
    out = engine.request_publish(body.slug, body.note)
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=out.get("error", "فشل الطلب"))
    return out


@app.post("/approvals/{aid}/decide")
def decide(aid: int, body: DecideIn):
    out = engine.decide_publish(aid, body.decision, body.note)
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=out.get("error", "فشل القرار"))
    return out


@app.get("/reports")
def reports(limit: int = 50):
    return get_store().list_reports(limit=limit)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("kidbook.api:app", host="0.0.0.0", port=8700, log_level="info")
