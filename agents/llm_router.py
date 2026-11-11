"""LLM Router integration — provider health check + status reporting.

Env vars:
  LLM_ROUTER_API_KEY     — the router bearer/key (never logged, never sent to frontend)
  LLM_REASONING_PROVIDER — optional model override (default: the router's default)
  LLM_PROVIDER — set to "llm_router" to enable this provider end-to-end

Never prints or returns the key. The founder's dashboard only shows:
  { configured: bool, provider: "llm_router", model: str, health: { ok, latency_ms, error? } }
"""
from __future__ import annotations
import logging
import os
import time

log = logging.getLogger("ai-business-hq.llm_router")

ROUTER_ENV = ("LLM_ROUTER_API_KEY", "LLM_ROUTER_BASE_URL", "LLM_ROUTER_MODEL")


def router_env_status() -> dict:
    return {
        k: bool((os.getenv(k) or "").strip()) for k in ROUTER_ENV
    }


def router_available() -> bool:
    """True only when ALL router vars are set — the user has opted-in explicitly."""
    return all(router_env_status().values())


def router_model() -> str:
    return (os.getenv("LLM_ROUTER_MODEL") or "").strip()


def health_check() -> dict:
    """Send a MINIMAL request through the router. Never called by tests."""
    if not router_available():
        return {
            "ok": False,
            "configured": False,
            "error": "LLM_ROUTER_* not set — provider is not configured.",
            "latency_ms": None,
            "model": None,
        }

    import httpx
    base = (os.getenv("LLM_ROUTER_BASE_URL") or "").rstrip("/")
    headers = {"Authorization": f"Bearer {os.getenv('LLM_ROUTER_API_KEY')}",
               "Content-Type": "application/json"}
    model = router_model()
    payload = {
        "model": model,
        "messages": [{"role": "system",
                      "content": "You are an availability probe. Reply with exactly: OK"},
                     {"role": "user",
                      "content": "Probe"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    start = time.monotonic()
    try:
        r = httpx.post(f"{base}/chat/completions", headers=headers,
                       json=payload, timeout=20)
        latency_ms = int((time.monotonic() - start) * 1000)
        ok = r.status_code == 200
        body_excerpt = (r.text or "")[:120] if not ok else None
        return {
            "ok": ok,
            "configured": True,
            "model": model,
            "base_url_configured": bool(base),
            "latency_ms": latency_ms,
            "error": None if ok else f"http {r.status_code}: {body_excerpt}",
        }
    except Exception as e:  # noqa: BLE001
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "ok": False,
            "configured": True,
            "model": model,
            "latency_ms": latency_ms,
            "error": str(e)[:200],
        }
