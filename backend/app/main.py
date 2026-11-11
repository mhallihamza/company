"""AI Business HQ — unified FastAPI entry point.
Run from the project root:
    .\\.venv\\Scripts\\uvicorn.exe backend.app.main:app --port 8700 --reload
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app import config

log = logging.getLogger("ai-business-hq")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agents import registry  # noqa: PLC0415
    from backend.app.db import get_store  # noqa: PLC0415
    from backend.app.routers.profiles import seed as _seed_profiles  # noqa: PLC0415
    log.info("platform started — %d departments registered", len(registry.list_departments()))
    db = get_store()
    log.info("database: %s", db.backend_label)
    if db.pg_diag:
        log.warning("db diag: %s", db.pg_diag)
    try:
        _seed_profiles()
        log.info("market profiles seeded (us-en, fr-fr, sa-en)")
    except Exception as e:  # noqa: BLE001
        log.warning("profile seed failed: %s", e)
    _maybe_scheduler()
    yield


app = FastAPI(title="AI Business HQ", version="3.3.0",
              description="CEO Agent + admin departments — LangGraph + FastAPI + Supabase",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.routers import (agents, approvals, books, capabilities, ceo,  # noqa: E402
                                 departments, health, observability, opportunities,
                                 profiles, reports, settings, tests)

for mod in (health, ceo, departments, books, opportunities, approvals, reports,
            settings, agents, observability, capabilities, tests, profiles):
    app.include_router(mod.router, prefix="/api")


def _maybe_scheduler() -> None:
    """APScheduler gate: runs daily_research every day at 08:00 when enabled in .env."""
    if not config.FEATURE_SCHEDULER:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler  # noqa: PLC0415
    except ImportError:
        log.warning("ENABLE_SCHEDULER set but apscheduler is not installed — skipped")
        return
    from agents.workflows import daily_research  # noqa: PLC0415

    scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "Europe/Berlin"))
    scheduler.add_job(daily_research.run, "cron", hour=8, minute=0,
                      id="daily_research", replace_existing=True)
    scheduler.start()
    log.info("morning scheduler enabled (08:00)")


@app.get("/")
def root():
    return {"name": "AI Business HQ", "version": "3.3.0", "docs": "/docs",
            "api": "/api/health"}
