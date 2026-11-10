"""Marketplace integrations — real-Etsy paths ported from the legacy agent.

`etsy_active_listings()` — search active listings with x-api-key to get the REAL
count + top-25 favorers + average price when ETSY_KEYSTRING (or legacy ETSY_API_KEY)
is present. Otherwise callers get a clearly-labelled `demo` source with no numbers.

`etsy_create_draft()` — full publish flow (listing + file + cover image) gated by
the human-approval lane. Without keys it raises a structured `EtsyError`. Real
failure always surfaces status code + body — never an invented listing id.

Auth: Etsy v3 expects `x-api-key` in the format `keystring:shared_secret` when
the shared secret is configured. OAuth is via refresh-token flow
(`POST /v3/public/oauth/token`). Access tokens expire in about one hour; we refresh
before expiry *and* once after a 401, then retry.

Env (.env):
  ETSY_KEYSTRING          — the keystring (preferred). Legacy alias: ETSY_API_KEY.
  ETSY_SHARED_SECRET      — REQUIRED together with the keystring.
  ETSY_ACCESS_TOKEN       — short-lived access token (refreshed on demand).
  ETSY_REFRESH_TOKEN      — long-lived refresh token.
  ETSY_SHOP_ID            — numeric shop id.
  ETSY_TAXONOMY_ID        — taxonomy for a "download" listing (default: printable book).
"""
from __future__ import annotations
import json
import os
import threading
import time
from typing import Any, Optional

_ETSY = "https://openapi.etsy.com/v3/application"
_TOKEN_ENDPOINT = "https://api.etsy.com/v3/public/oauth/token"
_MOCK_LISTINGS = 23801
TOKEN_GRACE_S = 60

# In-memory cache so we don't hit the token endpoint on every call (or every test).
_state_lock = threading.Lock()
_state: dict[str, Any] = {"token": None, "expires_at": 0.0}


def _read_env() -> dict[str, str]:
    keystring = os.getenv("ETSY_KEYSTRING") or os.getenv("ETSY_API_KEY") or ""
    shared_secret = os.getenv("ETSY_SHARED_SECRET", "")
    access_token = os.getenv("ETSY_ACCESS_TOKEN", "")
    refresh_token = os.getenv("ETSY_REFRESH_TOKEN", "")
    shop_id = os.getenv("ETSY_SHOP_ID", "")
    taxonomy_raw = os.getenv("ETSY_TAXONOMY_ID", "")
    try:
        taxonomy_id = int(taxonomy_raw) if taxonomy_raw else 0
    except ValueError:
        taxonomy_id = 0
    return {
        "keystring": keystring,
        "shared_secret": shared_secret,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "shop_id": shop_id,
        "taxonomy_id": taxonomy_id,
    }


def _api_key_header(cfg: dict[str, str]) -> str:
    """x-api-key header value: `keystring:shared_secret` (current Etsy v3 format)."""
    if cfg["shared_secret"]:
        return f"{cfg['keystring']}:{cfg['shared_secret']}"
    return cfg["keystring"]


def _config_summary() -> dict[str, str]:
    """Safe log summary — never includes secrets."""
    cfg = _read_env()
    return {
        "keystring_set": "true" if cfg["keystring"] else "false",
        "shared_secret_set": "true" if cfg["shared_secret"] else "false",
        "access_token_set": "true" if cfg["access_token"] else "false",
        "refresh_token_set": "true" if cfg["refresh_token"] else "false",
        "shop_id": cfg["shop_id"] or "",
    }


def _auth_headers(cfg: dict[str, str]) -> dict[str, str]:
    return {
        "x-api-key": _api_key_header(cfg),
        "Authorization": f"Bearer {cfg['access_token']}",
        "Accept": "application/json",
    }


def _san(msg: str, cfg: Optional[dict[str, str]] = None) -> str:
    """Sanitize a log line — strip anything that might look like a secret."""
    secret_like = [
        cfg["keystring"] if cfg else "",
        cfg["shared_secret"] if cfg else "",
        cfg["access_token"] if cfg else "",
        cfg["refresh_token"] if cfg else "",
    ]
    out = msg
    for token in secret_like:
        if token:
            out = out.replace(token, "[redacted]")
    for bad in ("&client_secret=", "&refresh_token=", "&access_token=", "client_secret=",
                "refresh_token=", "access_token=", "client_id="):
        # defensive: even if a raw secret slipped into the message, redact its value
        idx = out.find(bad)
        if idx != -1:
            start = idx + len(bad)
            end = out.find("&", start)
            if end == -1:
                end = len(out)
            out = out[:start] + "[redacted]" + out[end:]
    return out


def _log_failure(operation: str, status_code: int | str, body: Any,
                 cfg: Optional[dict[str, str]] = None) -> None:
    try:
        if not isinstance(body, str):
            body_s = json.dumps(body, ensure_ascii=False)[:800]
        else:
            body_s = body[:800]
    except Exception:  # noqa: BLE001
        body_s = str(body)[:800]
    print(f"[etsy] FAIL {operation} status={status_code} body={_san(body_s, cfg)}",
          flush=True)


def _request(cfg: dict[str, str], method: str, path: str,
             *, params: Optional[dict] = None, data: Optional[dict] = None,
             files: Optional[dict] = None, timeout: int = 30) -> Any:
    """Single HTTP call — raises requests.HTTPError on non-2xx."""
    import requests

    url = f"{_ETSY}{path}"
    kwargs: dict[str, Any] = {"headers": _auth_headers(cfg), "timeout": timeout}
    if params is not None:
        kwargs["params"] = params
    if data is not None:
        kwargs["data"] = data
    if files is not None:
        kwargs["files"] = files

    r = requests.request(method, url, **kwargs)
    if not (200 <= r.status_code < 300):
        body_text = r.text if isinstance(r.text, str) else str(r.text)
        _log_failure(f"{method} {path}", r.status_code, body_text, cfg)
        r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return {"raw": r.text}


def _token_request(cfg: dict[str, str]) -> dict[str, Any]:
    import requests

    client_id = cfg["keystring"]
    client_secret = cfg["shared_secret"] or cfg["refresh_token"]  # fallback: allow refresh-only
    if not client_id:
        raise RuntimeError("ETSY_KEYSTRING / ETSY_API_KEY is not configured")

    body = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": cfg["refresh_token"],
    }
    if cfg["shared_secret"]:
        body["client_secret"] = cfg["shared_secret"]

    r = requests.post(_TOKEN_ENDPOINT, data=body, timeout=30)
    if not (200 <= r.status_code < 300):
        _log_failure("oauth/refresh", r.status_code, r.text, cfg)
        r.raise_for_status()
    return r.json()


def _ensure_fresh_token(cfg: dict[str, str]) -> bool:
    """Refresh if expired or within grace; returns True if we have a token, False otherwise."""
    with _state_lock:
        cached_token = _state["token"]
        cached_exp = float(_state["expires_at"] or 0)
    if cached_token and time.time() < cached_exp - TOKEN_GRACE_S:
        cfg["access_token"] = cached_token
        return True
    return _refresh_token(cfg)


def _refresh_token(cfg: dict[str, str]) -> bool:
    with _state_lock:
        # re-check inside lock — if another thread refreshed, reuse
        if _state["token"] and time.time() < float(_state["expires_at"]) - TOKEN_GRACE_S:
            cfg["access_token"] = _state["token"]
            return True
        if not cfg["refresh_token"]:
            return False
        data = _token_request(cfg)
        token = data.get("access_token", "")
        expires_in = int(data.get("expires_in", 3600))
        if not token:
            _log_failure("oauth/refresh", "200", data, cfg)
            return False
        _state["token"] = token
        _state["expires_at"] = time.time() + expires_in
        cfg["access_token"] = token
        return True


def etsy_active_listings(keywords: list[str]) -> dict[str, Any]:
    """Real competition read from Etsy Open API v3 (needs ETSY_KEYSTRING + ETSY_SHARED_SECRET)."""
    cfg = _read_env()
    key = cfg["keystring"]
    if not key:
        return {"source": "demo", "reason": "ETSY_KEYSTRING not set", "keywords": {}}
    try:
        import requests  # noqa: F401
    except ImportError:
        return {"source": "demo", "reason": "requests not installed", "keywords": {}}

    out: dict[str, Any] = {"source": "etsy_api_v3", "keywords": {}}
    for kw in [k for k in keywords if k][:6]:
        try:
            r = requests_call_etsy("GET", "/listings/active", cfg,
                                   params={"keywords": kw, "limit": 25, "sort_on": "score"},
                                   timeout=20)
            results = r.get("results") or []
            favorers = [x.get("num_favorers", 0) or 0 for x in results]
            prices = [float(x["price"]["amount"]) / x["price"]["divisor"]
                      for x in results if x.get("price")]
            out["keywords"][kw] = {
                "source": "etsy_api_v3",
                "total_listings": r.get("count"),
                "avg_favorers_top25": round(sum(favorers) / max(len(favorers), 1), 1),
                "avg_price_top25": round(sum(prices) / max(len(prices), 1), 2) if prices else None,
            }
        except Exception as e:  # noqa: BLE001
            # never silently merge sample data into a real result; tag partial with the reason
            out["keywords"][kw] = {"source": "partial", "query": kw, "error": str(e)[:200]}
    return out


def requests_call_etsy(method: str, path: str, cfg: dict[str, str],
                       **kwargs) -> dict[str, Any]:
    """Peculiar wrapper so etsy_active_listings doesn't need OAuth (read-only)."""
    import requests

    params = kwargs.pop("params", None)
    data = kwargs.pop("data", None)
    headers = {
        "x-api-key": _api_key_header(cfg),
        "Accept": "application/json",
    }
    url = f"{_ETSY}{path}"
    r = requests.request(method, url, headers=headers, params=params, data=data,
                         timeout=kwargs.get("timeout", 30))
    if not (200 <= r.status_code < 300):
        body_text = r.text if isinstance(r.text, str) else str(r.text)
        _log_failure(f"{method} {path}", r.status_code, body_text, cfg)
        r.raise_for_status()
    return r.json()


def _attempt_once(cfg: dict[str, str], meta: dict[str, Any], pdf_path: str,
                  cover_path: str | None, price: float) -> str:
    listing_body = {
        "quantity": 999,
        "title": str(meta.get("title", "")).strip()[:140],
        "description": meta.get("description", ""),
        "price": float(price),
        "who_made": "i_did",
        "when_made": "made_to_order",
        "type": "download",
        "taxonomy_id": cfg["taxonomy_id"] or 0,
        "tags": ",".join((meta.get("tags") or [])[:13]),
        "is_supply": False,
    }
    created = _request(cfg, "POST", f"/shops/{cfg['shop_id']}/listings",
                       data=listing_body, timeout=60)
    listing_id = str(created.get("listing_id"))
    if not listing_id:
        raise RuntimeError(f"Etsy listing creation returned no listing_id: {created}")

    with open(pdf_path, "rb") as f:
        _request(cfg, "POST", f"/shops/{cfg['shop_id']}/listings/{listing_id}/files",
                 files={"file": f}, data={"name": os.path.basename(pdf_path)},
                 timeout=180)

    if cover_path and os.path.exists(cover_path):
        with open(cover_path, "rb") as f:
            _request(cfg, "POST", f"/shops/{cfg['shop_id']}/listings/{listing_id}/images",
                     files={"image": f}, timeout=180)

    return listing_id


def _http_status(exc: BaseException) -> int:
    """Pull HTTP status code out of a requests exception or HTTPError."""
    resp = getattr(exc, "response", None)
    if resp is not None and getattr(resp, "status_code", None) is not None:
        try:
            return int(resp.status_code)
        except (TypeError, ValueError):
            return 0
    return 0


class EtsyError(RuntimeError):
    """Structured wrapper — status_code preserved for the caller to route on."""

    def __init__(self, message: str, status_code: int | str = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


def etsy_create_draft(meta: dict[str, Any], pdf_path: str, cover_path: str | None,
                      price: float | None = None) -> dict[str, Any]:
    """Full real flow: listing → PDF file → cover image.

    Returns ``{"ok": True, "listing_id": str, "shop_id": str}`` on success, or raises
    :class:`EtsyError` on any failure. No mock ids are ever returned. The caller is
    responsible for marking a book ``draft_created`` on success, or ``draft_failed``.
    """
    cfg = _read_env()
    if not cfg["keystring"]:
        raise EtsyError("Etsy not configured: ETSY_KEYSTRING is not set", 0)
    if not cfg["shop_id"]:
        raise EtsyError("Etsy not configured: ETSY_SHOP_ID is not set", 0)
    if not cfg["access_token"] and not cfg["refresh_token"]:
        raise EtsyError("Etsy not configured: neither ETSY_ACCESS_TOKEN nor ETSY_REFRESH_TOKEN is set", 0)

    price = float(price if price is not None else float(os.getenv("DEFAULT_BOOK_PRICE_USD", "4.99")))

    if not _ensure_fresh_token(cfg):
        raise EtsyError("Etsy OAuth refresh failed; check ETSY_REFRESH_TOKEN and ETSY_SHARED_SECRET", 401)

    for attempt in ("first", "retry"):
        try:
            listing_id = _attempt_once(cfg, meta, pdf_path, cover_path, price)
            return {"ok": True, "listing_id": listing_id, "shop_id": cfg["shop_id"]}
        except Exception as exc:  # noqa: BLE001 — normalize every failure to EtsyError
            code = _http_status(exc)
            if attempt == "first" and code in (401, 403):
                _log_failure("create_draft:first_attempt", code, str(exc), cfg)
                if _refresh_token(cfg):
                    continue
            _log_failure(f"create_draft:{attempt}", code or "n/a", str(exc), cfg)
            raise EtsyError(f"Etsy draft failed: {exc}", code) from exc


def kdp_manifest(story: dict[str, Any]) -> dict[str, Any]:
    etsy = story.get("etsy") or {}
    return {
        "title": etsy.get("title", story.get("title", "Untitled")),
        "description": etsy.get("description", ""),
        "tags": etsy.get("tags", [])[:13],
        "note": "KDP has no general book-upload API; paste this manifest into KDP manually.",
    }


# self-reference helper used by the capability registry test path
import agents.capabilities as _capabilities_pkg  # noqa: F401,E402
from agents.capabilities import CapabilitySpec, register_capability

register_capability(CapabilitySpec(
    id="marketplace_listings",
    title_en="Marketplace Listings", title_ar="قوائم الأسواق",
    description_en="Etsy competition read + full draft upload (Etsy v3 OAuth). No mocks when unconfigured.",
    description_ar="قراءة منافسة Etsy + رفع مسودة كاملة (Etsy v3 OAuth). بدون محاكاة دون مفاتيح.",
    used_by=["books.publishing"], deterministic=True,
))
