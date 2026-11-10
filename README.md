# AI Business HQ — an AI company operating system

> **AI Business HQ is the founder's control plane for an AI-run business:**
> one **CEO agent** (LangGraph orchestrator) that understands goals,
> **delegates to registered departments**, tracks execution, and returns
> a report — asking **your** sign-off before any external effect.

The UI is English-only (Arabic support was removed by founder request).

## Architecture

> **Deep-dive doc for engineers: `ARCH.md`** — layer map, every router, the CEO graph, market-profile
> contract, the truthfulness rules (why nothing fake ever reaches the store), how to add a department /
> market / capability, ops playbook and known boundaries.

```
┌───────────────────────────────────────────────────────────────┐
│  Founder — you (goals, reports, approvals)                   │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│  Frontend — Next.js 15 (TypeScript + Tailwind, App Router)    │
│  /dashboard · /ceo · /departments · /agents                   │
│  /capabilities · /books · /profiles · /products               │
│  /opportunities · /approvals · /reports                       │
│  /observability · /settings  — EN default + AR toggle         │
└───────────────────────┬───────────────────────────────────────┘
                        │ fetch (Bearer FOUNDER_TOKEN)
┌───────────────────────▼───────────────────────────────────────┐
│  Backend — FastAPI (the API gateway, port 8700)               │
│  /api/health (public {status:"ok"})  /api/admin/health        │
│  /api/ceo/run /api/departments /api/agents /api/capabilities  │
│  /api/observability /api/tests /api/profiles /api/books      │
│  /api/opportunities /api/approvals /api/reports /api/settings │
│  bearer auth, CORS for :3000                                  │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│  Agents — LangGraph (agents/ — separate from the API)         │
│                                                               │
│                   🤵 CEO (agents/ceo/graph.py)                 │
│       ┌───────┬────────┬──────────┬────────┬───┐               │
│  Books  Intel.  Affiliate  Marketing Finance  QA …             │
│                                                               │
│  Departments = supervisor subgraphs with their own agents     │
│  Capabilities (agents/capabilities/) — shared services        │
│  Registry (agents/registry.py) — plug-and-play departments    │
│  Fees (agents/fees/) — verified Etsy/KDP formulas             │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│  Data — Supabase Postgres (auto) → SQLite fallback            │
│  tasks · executions · opportunities · products                 │
│  reports · approvals · audit_logs · budgets                    │
│  settings · product_tests · market_profiles                   │
└─────────────────────────────────────────────────────────────────┘
```

## Repository layout

```
ai-business-hq/
├── frontend/            Next.js 15 (TypeScript + Tailwind) — EN default + AR toggle
├── backend/             FastAPI: app/routers/* · app/services/* · app/db.py
│   ├── Dockerfile
│   ├── requirements.txt (pinned)
│   └── requirements-dev.txt
├── agents/              LangGraph — CEO + departments + capabilities + fees
│   ├── ceo/             CEO graph (plan → route → execute → evaluate → close)
│   ├── departments/     books/ market_intel/ affiliate/ marketing/ finance/ qa/ product/ design/
│   ├── capabilities/    web_research · content_generation · image_generation · pdf_generation
│   │                    marketplace_listings · opportunity_scoring · unit_economics · qa_checks
│   ├── fees/            etsy.py · kdp.py — verified (source_url + last_reviewed) · registry.py
│   ├── localization/    Per-language story prompts (en/fr) · fonts · text direction · QA rules
│   ├── workflows/       opportunity_engine.py · daily_research.py · publishing.py
│   ├── profiles.py      pick enabled market profile (fail-fast when disabled/unknown)
│   ├── registry.py      DepartmentSpec + AgentSpec
│   ├── llm.py           Provider factory + resilient wrapper + deterministic demo model
│   └── common.py        Supervisor helpers (LLM routing with deterministic fallback)
├── tests/               pytest — currently 111 offline tests
├── database/schema.sql  Reference schema (reference only; migrations run at boot)
├── docker-compose.yml   backend + frontend
├── fonts/Amiri-Regular.ttf   Bundled font for the PDF pipeline (Latin coverage)
```

> `archive/` was removed from the tree in Phase 7 — the historical pre-HQ code is
> preserved on the `archive-legacy` branch, tagged `archive-legacy-v0.1.0`.
> It is referenced here for review only and is not imported or built.

## The registered departments

| key | Department | What it does | Approval gate |
| --- | --- | --- | --- |
| `books.market` | Books — Market | Trends + Etsy → English opportunity report | none |
| `books.content` | Books — Content | Idea → story → images → PDF | story review |
| `books.publishing` | Books — Publish | Etsy draft after **your** approval | human required |
| `intelligence` | Market Intelligence | Niche scan + scored opportunities (0-10) | none |
| `affiliate` | Affiliate Marketing | Public affiliate products + Python economics | before publish |
| `marketing` | Marketing & SEO | SEO / listing copy / Pinterest / calendar | before publish |
| `finance` | Finance & Margins | Etsy/KDP fees + unit economics (Python only) | none |
| `qa` | QA & Compliance | PASS/FAIL preflight gate | gate |
| `product` | Product Development | Opportunity → candidate product | none |
| `design` | Design Studio | Image provider hook (stub) | before publish |

Every department ships with **agent cards** (reasoning / fast / deterministic tiers) at
`GET /api/agents` — rendered on the **Agent Cards** page (`/agents`).

## Verified capabilities (each carries source_url + last_reviewed)

| Capability | Consumed by | Deterministic? |
| --- | --- | --- |
| web_research | books.market, intelligence, affiliate | yes |
| content_generation | books.content, books.market, marketing, intelligence | LLM + Python validation |
| image_generation | books.content, design | PIL (fallback) or OpenAI GPT-Image |
| pdf_generation | books.content | yes |
| marketplace_listings | books.publishing | real only with ETSY_KEYSTRING+SECRET+REFRESH+SHOP |
| opportunity_scoring | affiliate, intelligence, product | yes |
| unit_economics | finance, affiliate | yes — fee model in `agents/fees/` |
| qa_checks | qa, books.content | yes |

## Golden rules — each enforced by a test

1. **No external action without your sign-off.** Enforced by `tests/test_approval_gate.py`
   and `tests/test_phase1_etsy.py` (unauthenticated → 401; no Etsy config → 502 + `draft_failed`, never `published`).
2. **No fabricated numbers.** Enforced by `tests/test_phase3_fees.py` (hand-calculated Etsy/KDP fixtures)
   and `tests/test_phase2_gates.py` (no demo opportunity is stored as `live` without explicit gate).
3. **Every run is audited.** Enforced by `tests/test_hq_routes_and_observability` (in `tests/test_hq.py`) —
   `/api/observability` reads the database directly and the counts back the test.
4. **Source is labelled.** Enforced by `tests/test_phase2_gates.py` (`AIHQ_ALLOW_DEMO=0` → no opportunity written).

## Quick start

```powershell
# 1) Configure
copy .env.example .env   # set MISTRAL_API_KEY + FOUNDER_TOKEN (+ optional DATABASE_URL)

# 2) Backend (terminal 1)
.\.venv\Scripts\uvicorn.exe backend.app.main:app --port 8700 --reload

# 3) Frontend (terminal 2)
cd frontend
npm install
npm run build && npm start    # http://localhost:3000
# or npm run dev for development

# 4) Offline tests (no network, no keys)
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

### Docker

```bash
FOUNDER_TOKEN=$(openssl rand -hex 32) docker compose up --build
```

### Scheduled morning brief

```powershell
ENABLE_SCHEDULER=1 .\.venv\Scripts\uvicorn.exe backend.app.main:app
```

## Talking to the CEO

Through the UI — http://localhost:3000/ceo (English).
Or via the API — http://localhost:8700/docs.

```powershell
curl -X POST http://localhost:8700/api/ceo/run `
  -H "Authorization: Bearer YOUR_FOUNDER_TOKEN" `
  -H "Content-Type: application/json" `
  -d "{\"task\": \"analyze the children's-book market\"}"
```

## Languages

English-only. Arabic support, RTL layout, Arabic routing keywords and Arabic LLM prompts were
removed by founder request. The legacy rows SA/ar in `market_profiles` are migrated to SA/en at boot.
The language adapter module still supports fr-fr (French) alongside en (English).

## Notes & honesty

- **Archive is no longer a project.** The old `legacy/` and pre-HQ code was moved out of `main`;
  it lives on the `archive-legacy` branch, tagged `archive-legacy-v0.1.0`. Nothing there runs or is imported.
- **Etsy** — without `ETSY_KEYSTRING` + `ETSY_SHARED_SECRET` + `ETSY_REFRESH_TOKEN` + `ETSY_SHOP_ID`,
  the **publish flow fails hard with a structured error** (HTTP 502) and the product stays `draft_failed`. No listing is ever created without explicit founder sign-off.
- **LLM** — Mistral free tier hits 429. The `ResilientChatModel` **falls back to deterministic replies
  and labels the note** in the UI (`llm_note`).
- The product is domain-agnostic — Books was the first department, not the identity of the system.
- **Demo mode** — `AIHQ_ALLOW_DEMO=1` enables clearly-labelled demo output. Without it, demo data is blocked at the gate.
