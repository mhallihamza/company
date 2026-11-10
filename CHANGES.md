# CHANGES — AI Business HQ 3.2.0 (Phases 1–6 + 7-Item 1)

## Honesty correction (Item 2, Phase 7)

Earlier release claimed "No real Etsy publisher implemented." Corrected:

- Real Etsy path **is implemented** in `agents/capabilities/marketplace.py` (publishing listing → file → cover image after founder approval).
- It has **not been exercised against a live Etsy shop** yet — no live listing has been created from this codebase.
- Integration depends on the canonical env names: `ETSY_KEYSTRING`, `ETSY_SHARED_SECRET`, `ETSY_REFRESH_TOKEN`, `ETSY_SHOP_ID` (Item 1 unified them). `ETSY_API_KEY` remains supported as a deprecated alias.

## Verification status

| Area | Implemented | Tested offline | Verified against a live store |
|---|---|---|---|
| Etsy publish flow | ✅ | ✅ (mocked HTTP) | ❌ — not yet |
| Etsy competition read | ✅ | ✅ (partial when unconfigured) | ❌ — not yet |
| Unit economics (Etsy/KDP) | ✅ | ✅ (hand-calc fixtures) | n/a |
| Opportunity engine | ✅ | ✅ (dedupe, scoring) | n/a |
| Market profiles (us-en / fr-fr / sa-ar) | ✅ seeded | ✅ (conftest seeded) | n/a |
| Approval gate enforcement | ✅ | ✅ (`test_approval_gate.py`) | n/a |
| Budget cap | ✅ | ✅ | n/a |
| `/api/health` sanitization | ✅ | ✅ | n/a |
| Storage excluded from git | ✅ | n/a | n/a |
| Docker compose (env passthrough) | ✅ | n/a | n/a |
| Source badges (live/partial/demo) | ✅ | ✅ | n/a |
| Language adapters (localization) | ❌ pending Item 7 | ❌ | ❌ |
| Fee-model per marketplace region | ❌ pending Item 7 | ❌ | ❌ |
| Background workers / task queue | ❌ not yet | ❌ | ❌ |
| Frontend tests | ❌ not yet | ❌ | ❌ |

## Items shipped

### Phase 1 — Etsy publishing truthfulness
- `agents/capabilities/marketplace.py`: real HTTP Etsy v3 with `x-api-key` in `keystring:shared_secret` format.
- OAuth refresh-token flow — refresh before expiry *and* once after a 401.
- No mock/fallback ids ever returned — raises `EtsyError` with status code + context on any failure.
- `services/store.py`: adds `publish_targets` and `price_usd` columns safely, no errors when already present.
- `products` table: `price_usd REAL DEFAULT 4.99` — the price is never invented at publish time.

### Phase 2 — Demo labelling + gating
- `opportunities` and `reports` tables: `source TEXT` and `evidence TEXT`.
- `intelligence.scorer` refuses to write fake opportunities when no live keys. Opt-in via `AIHQ_ALLOW_DEMO=1`.
- UI `SourceBadge` on opportunities and reports (live / partial / demo).
- `tests/test_phase2_gates.py` (6 tests, offline).

### Phase 3 — Verified fee models
- New `agents/fees/` module: `etsy.py` (listing $0.20, transaction 6.5%, payment 3.0% + $0.25 US),
  `kdp.py` (paperback royalty 50/60% threshold $9.99, printing $2.15 base + $0.012/page above 108).
- Every rule has `source_url` and `last_reviewed=2026-11-09`.
- `unit_economics()` now reflects true Etsy costs and KDP math; reports carry source URLs inline.

### Phase 4 — Opportunity engine (partial)
- New `agents/workflows/opportunity_engine.py`: LangGraph Discover → Evidence → Score → Dedupe → Explain.
  Dedupes by `(niche, language, country)`; scores clamped 0-10 and tied to fee-model margin.
- New `/api/tests`: capture real post-publish signal (views / favorites / sales).
- New `/api/profiles`: list / create / toggle `market_profiles` (seeds us-en / fr-fr / sa-ar).

### Phase 5 — Multi-market architecture (foundational)
- `market_profiles` table seeded.
- Seeds: us-en, fr-fr, sa-ar (RTL + Amiri). No per-market adapters yet — capability shape exists, implementation pending Item 7.

### Phase 6 — Security + reliability
- `/api/health`: returns only `{status: "ok"}`; detailed view moved to `/api/admin/health` (requires founder token).
- `human_confirmed` body is no longer honored — every publish path requires an approval row.
- `list_tasks` / `list_executions` / `/audit`: caps enforced.
- `hmac.compare_digest` for founder token; USD monthly budget cap enforced at task creation time.
- Storage paths removed from git; `.env.example` updated; Docker passes the full env explicitly.
- Dependencies pinned and split (backend + requirements-dev).

### Phase 7 — Item 1 (Etsy config unified)
- Item 1 of `Phase 7` done: canonical `ETSY_KEYSTRING` / `ETSY_SHARED_SECRET` / `ETSY_REFRESH_TOKEN` / `ETSY_SHOP_ID`.
  `ETSY_API_KEY` remains supported as a deprecated alias (single warning per process).
- `etsy_config_status()` helper returns booleans only (never values); wired into `/api/admin/health` and Settings UI.
- Settings UI renders a green/gray badge per variable (EtsyConfigured / not configured).

## Known limits / what's still on the board

- Etsy integration **not yet verified against a live Etsy shop**.
- Phase 5 adapters are a surface only — seasonal calendar-driven scorer is not yet wired (Item 7).
- No real-time workers — 12-image books will still block the HTTP request shape.
- Budget tracking counts estimated spend-per-task, not LLM tokens directly.
- Localization UI tests pending (Item 7).
- French/Arabic strings for the newly-added UI text pending Item 7.
