"""FOUNDER_TOKEN بسيط — حماية أثناء التطوير؛ استبدله لاحقاً بـ NextAuth/Supabase Auth."""
from __future__ import annotations
import os

from fastapi import Header, HTTPException


def require_founder(authorization: str | None = Header(default=None)) -> str:
    expected = os.getenv("FOUNDER_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=500,
                            detail="FOUNDER_TOKEN is not set in .env — set it before launching the UI")
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or token != expected:
        raise HTTPException(status_code=401, detail="invalid founder token")
    return token
