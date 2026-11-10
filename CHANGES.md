# CHANGES — AI Business HQ 3.1.0 (Phases 1–6)

Honest release notes. What actually changed, and what remains beyond this commit.

## Phase 1 — Etsy publishing truthfulness
- `agents/capabilities/marketplace.py`: real HTTP Etsy v3 with `x-api-key` in `keystring:shared_secret` format
  when `ETSY_SHARED_SECRET` is set. OAuth refresh-token flow (refresh before expiry *and* once after a 401)
  with retry. No mock/fallback ids ever returned — raises `EtsyError` with status code + context on any failure.
- `services/store.py`: `_ensure_schema` — adds `publish_targets` and `price_usd` columns safely, no errors when already present.
- `products` table: new `price_usd REAL DEFAULT 4.99` so the price is never invented at publish time.

## Phase 2 — Demo labelling + gating
- `opportunities` + `reports` tables: new `source TEXT` and `evidence TEXT` columns.
- `intelligence.scorer`: refuses to write fake opportunities when no live keys are available.
  Set `AIHQ_ALLOW_DEMO=1` to opt-in, but results always carry `source=demo`.
- UI: `SourceBadge` on opportunities and reports (live / partial / demo).
- `test_phase2_gates.py`: 6 new tests, all offline.

## Phase 3 — Verified fee models
- New `agents/fees/` module: `etsy.py` (listing 0.20, transaction 6.5%, payment 3.0% + $0.25 US),
  `kdp.py` (paperback royalty 50/60% threshold $9.99, printing $2.15 base + $0.012/page above 108).
- All figures carry `source_url` and `last_reviewed=2026-11-09`.
- `unit_economics()` now reflects true Etsy costs and KDP math; reports carry source URLs inline.

## Phase 4 — Opportunity engine (partial)
- New `agents/workflows/opportunity_engine.py`: LangGraph Discover → Evidence → Score → Dedupe → Explain.
  Dedupes by `(niche, language, country)` key; scores clamped 0-10 and tied to fee-model margin.
- New `/api/tests` (POST/GET `/tests/correlation`): real post-publish signal capture (views/favorites/sales).
- New `/api/profiles`: list/create/toggle `market_profiles` (seeds us-en / fr-fr / sa-ar).

## Phase 5 — Multi-market architecture (foundational, not complete)
- `market_profiles` table seeded. List/add/enable/disable via `/api/profiles`.
- Each department unchanged in this commit — the profile surface exists but `us-en`/`fr-fr`/`sa-ar`-specific
  adapters (fee refs, seasonal calendars, RTL fonts) are intentionally left for a follow-up commit.

## Phase 6 — Security, reliability, cleanup
- `/api/health`: returns only `{"status":"ok"}`. Detailed status moved to `/api/admin/health` (requires founder token).
- `human_confirmed` from request bodies is no longer honored — every approve flow must be an approval row in the DB.
- `list_tasks` / `list_executions` / `/audit` caps enforced.
- `hmac.compare_digest` used for founder token; `create_task` enforces a USD monthly budget ceiling.
- Storage paths removed from git; root-level `.env.example` updated; Docker passes the full env explicitly.
- Dependencies pinned and split (backend + `requirements-dev.txt`).

## Known limits / what's NOT in this commit
- No real-time task queue or background workers yet (runs are synchronous; 12-image books will still block the HTTP call).
- Phase 5 adapters are a surface only; paying customers in France/US specifically are not yet shaped.
- No real Etsy publisher — publishing still calls the real API only when ETSY_API_KEY + SHARED_SECRET + SHOP_ID + REFRESH_TOKEN are set. All else remains MOCK.
- Budget enforcement tracks estimated per-task spend; actual LLM token cost mapping is not yet wired.

## How to apply
1. Build & run: `docker compose up --build`
2. First commit after Phase 2 applied migrations to the SQLite/Postgres store automatically.

## `/api/health` contract (post-release)
```
GET /api/health  → {"status":"ok"}
```
Anything else requires `Authorization: Bearer $FOUNDER_TOKEN` (or use /admin/health).
