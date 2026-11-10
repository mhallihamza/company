# CHANGES — AI Business HQ 3.2.0 (Phases 1–6 + Phase 7 Items 1–6)

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
| Tokens recorded from provider usage metadata | ✅ (measured/unmeasured) | ✅ | ❌ — not yet exercised against a live paid LLM call |
| `autonomy_level` enforced | ✅ (API + CEO graph) | ✅ | n/a |
| Static security scan (bandit) | ✅ 29 → 28 findings listed below | n/a | n/a |
| Dependency audit (pip-audit) | ✅ no known vulnerabilities | n/a | n/a |
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

### Phase 7 — Item 3 (evidence validator) + Item 4 (single CEO router)
- `agents/validation/evidence.py`: `validate_brief(brief, evidence)` with 1e-6 numeric tolerance,
  `cited_evidence` field match, and sales/revenue-wording rejection when evidence only carries favorites.
- `opportunity_engine._explain` retries once with the violations list, else stores `rejected_by_validator`.
- `agents/ceo/routing.py`: one source of truth — word-boundary Latin match, Arabic normalization
  (diacritics stripped, alef/hamza unified, taa marbuta, definite article stripped), phrase support,
  specificity tie-breaker (affiliate > qa > finance). `graph.py` and `llm.py` both import from it.
- `Qatar` no longer routes to qa; `تابع` removed — regression tests in `test_item4_router.py`.

### Phase 7 — Item 5 (connection pool)
- `psycopg_pool.ConnectionPool` (min 1, max 5, env-configurable; `check=check_connection`;
  `max_idle=60`, `max_lifetime=300` so a Supabase-side drop never poisons later requests).
- No module-level shared PG connection; pool used on every cursor checkout.
- SQLite keeps a fresh per-call connection (thread-safe under 10-threads write storm, `test_item5_pool.py`).
- `_sanitize()` strips DSN/host/password/user before any logging; errors surface as `[redacted]`.
- `profiles` router now uses pool-aware `store._execute`.

### Phase 7 — Item 6 (dead settings + repo cleanup)
- `autonomy_level` is now enforced: level 0 = nothing runs; level 1 = intelligence / affiliate / finance /
  qa / books.market; level 2 = everything (publishing STILL needs an approvals row); level 3 = reserved.
  Enforced at `POST /api/departments/{key}/run` (403) **and** inside the CEO graph `_execute` node
  (blocked executions recorded as `status='blocked'`). Publishing gate unchanged — human_required +
  approvals table independently of autonomy level.
- `tokens_used` now comes from provider `usage_metadata` / `response_metadata.token_usage` when the
  provider returns it (Mistral/OpenAI). Absent metadata = **NULL, never an invented 0**.
  Fake/scripted model records `source='unmeasured'`. `/observability` reports
  `tokens_measured_total`, `executions_with_token_data`, `executions_unmeasured`, `tokens_source`
  and the flat $0.15-per-finished-task budget estimate, labelled `estimated`.
- `/observability` UI shows the measured/unmeasured split instead of a single opaque total.
- `archive/` removed from `main` — preserved verbatim on branch `archive-legacy`, tag `archive-legacy-v0.1.0`.
  `fix_slugs.py` was already absent (nothing imports or executes it). `storage/books` was already untracked and stays so.
- CEO `route_task` refactor-on-edit bug (`route_keywords` NameError) found and fixed during Item 6.

**Static scan (bandit 1.8.2, run on `agents/` + `backend/`):** 29 → 28 findings after the B101 fix.
None are injectable (all SQL f-strings use `int()`-coerced limits or placeholder constants) and none are
High severity. Honestly listed, not hidden:

| Code | Count | Location / verdict |
|---|---|---|
| B608 hardcoded_sql_expressions | 18 | f-string `LIMIT {int(limit)}` (int-coerced) and `{ph}` placeholder constants — Medium severity, Low confidence, not injectable |
| B110 try_except_pass | 9 | intentional best-effort paths (budget update, pool close, safe migration) — commented as such |
| B101 assert_used | 0 after fix | was `assert self._pool is not None` → defensive `RuntimeError` |
| B105 hardcoded_password_string | 1 | false positive — Etsy public OAuth endpoint URL constant, no credential |

Totals after fix: **0 High, 18 Medium, 10 Low.** `pip-audit --requirement backend/requirements.txt` → **No known vulnerabilities found**.

## Known limits / what's still on the board

- Etsy integration **not yet verified against a live Etsy shop**.
- Phase 5 adapters are a surface only — seasonal calendar-driven scorer is not yet wired (Item 7).
- No real-time workers — 12-image books will still block the HTTP request shape.
- Budget tracking uses a flat $0.15 per finished task estimate; provider LLM token metadata is recorded when the provider returns it (measured/unmeasured split, shown in `/observability`).
- Localization UI tests pending (Item 7).
- French/Arabic strings for the newly-added UI text pending Item 7.
