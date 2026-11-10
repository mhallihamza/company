"""FOUNDER_TOKEN — constant-time compare; always non-None fallback."""
from __future__ import annotations
import hmac
import os

from fastapi import Header, HTTPException


def require_founder(authorization: str | None = Header(default=None)) -> str:
    expected = os.getenv("FOUNDER_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=500,
                            detail="FOUNDER_TOKEN is not set in .env — set it before launching the UI")
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid founder token")
    return token
