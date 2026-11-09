# AI Business HQ — an AI company operating system

> **Not a KidBook Agent.** AI Business HQ is the founder's control plane for an AI-run business:
> one **CEO agent** (LangGraph orchestrator) that understands your goals, **delegates to registered
> departments**, tracks execution, and comes back with a report — asking **your** sign-off before any
> external effect.

The UI is English-first with Arabic one click away (sidebar top → `AR — العربية`).

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│  Founder — you (define goals, approve/reject, pay the bills)  │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│  Frontend — Next.js 15 (TypeScript + Tailwind, App Router)    │
│  /dashboard · /ceo · /departments · /agents · /capabilities   │
│  /books · /products · /opportunities · /approvals             │
│  /reports · /observability · /settings  · EN (default) + AR   │
└───────────────────────┬───────────────────────────────────────┘
                        │ fetch (Bearer FOUNDER_TOKEN)
┌───────────────────────▼───────────────────────────────────────┐
│  Backend — FastAPI (the API gateway, port 8700)               │
│  /api/health /ceo/run /departments /agents /capabilities      │
│  /observability /books /opportunities /approvals /reports     │
│  /settings /audit /tasks — bearer auth, CORS for :3000       │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│  Agents — LangGraph (agents/ directory, separate from backend)│
│                                                               │
│                    🤵 CEO (agents/ceo/graph.py)                │
│       ┌───────┬───────┬───────┬───────┬───────┐               │
│  Books  Intel.  Affil.  Market.  Finance  QA …                 │
│                                                               │
│  Each department = supervisor graph + its own agents            │
│  Capabilities (agents/capabilities/) shared by all departments │
│  Registry (agents/registry.py) — plug-and-play departments      │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│  Data — Supabase Postgres (auto) → SQLite local fallback       │
│  tasks · task_executions · opportunities · products           │
│  reports · approvals · audit_logs · budgets · settings         │
└─────────────────────────────────────────────────────────────────┘
```

## Repository layout

```
ai-business-hq/
├── frontend/            Next.js 15 (TypeScript + Tailwind) — EN default + AR toggle
├── backend/             FastAPI: app/routers/*, app/services/*, app/db.py
│   ├── Dockerfile
│   └── requirements.txt
├── agents/              LangGraph — CEO + departments + capabilities
│   ├── ceo/             CEO graph (plan → route → execute → evaluate → close)
│   ├── departments/     books/ market_intel/ affiliate/ marketing/ finance/ qa/ product/ design/
│   ├── capabilities/    web_research · content_generation · image_generation · pdf_generation
│   │                    marketplace_listings · opportunity_scoring · unit_economics · qa_checks
│   ├── workflows/       daily_research · opportunity_validation · product_creation · publishing
│   ├── registry.py      DepartmentSpec + AgentSpec
│   ├── llm.py           Provider factory + resilient wrapper + deterministic demo model
│   └── common.py        Supervisor helpers (LLM with deterministic fallback)
├── tests/               11 offline tests — run ~10s, no network, no keys
├── database/schema.sql  Reference schema (workspace_id-ready for multi-tenant)
├── docker-compose.yml   backend + frontend
├── fonts/Amiri-Regular.ttf   Arabic print font for the PDF pipeline
└── archive/             Historical code kept for reference — see ARCHIVE.md inside
```

## The ten registered departments

| key | Department | What it does | Approval gate |
| --- | --- | --- | --- |
| `books.market` | Books — Market | Google Trends + Etsy → Arabic opportunity report | none |
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

**Capabilities are reusable services** — declared by every department spec, listed at `GET /api/capabilities`:

| Capability | Consumed by | Deterministic? |
| --- | --- | --- |
| web_research | books.market, intelligence, affiliate | yes |
| content_generation | books.content, books.market, marketing, intelligence | LLM + Python validation |
| image_generation | books.content, design | PIL (mock) or OpenAI GPT-Image |
| pdf_generation | books.content | yes |
| marketplace_listings | books.publishing | MOCK without keys |
| opportunity_scoring | affiliate, intelligence, product | yes |
| unit_economics | finance, affiliate | yes |
| qa_checks | qa, books.content | yes |

## Golden rules

1. **No external action without your sign-off.** Approvals flow through the `approvals` table + `/approvals` UI.
2. **No fabricated numbers.** Finance runs pure Python. Reports carry uncertainty notes.
3. **All runs are audited** — `tasks`, `task_executions`, `audit_logs` (visible on `/observability`).
4. **Model per task** — reasoning model for thinking, deterministic Python for math.
5. **Observability from day one** — `/observability` reads the database directly.

## Quick start

```powershell
# 1) Configure
copy .env.example .env   # set MISTRAL_API_KEY + FOUNDER_TOKEN

# 2) Backend (terminal 1)
.\.venv\Scripts\uvicorn.exe backend.app.main:app --port 8700 --reload

# 3) Frontend (terminal 2)
cd frontend
npm install
npm run build && npm start    # http://localhost:3000
# or npm run dev for development

# 4) Offline tests
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

### Docker

```bash
FOUNDER_TOKEN=$(openssl rand -hex 32) docker compose up --build
```

### Scheduled morning brief

```powershell
ENABLE_SCHEDULER=1 TZ=Europe/Berlin uvicorn backend.app.main:app
# daily_research.run() fires at 08:00 — requires apscheduler (already in requirements)
```

## Talking to the CEO

Through the UI — http://localhost:3000/ceo (Arabic or English).
Through the API — http://localhost:8700/docs.

```powershell
curl -X POST http://localhost:8700/api/ceo/run ^
  -H "Authorization: Bearer YOUR_FOUNDER_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"task\": \"analyze the children's-book market\"}"
```

## Languages

English is the default; Arabic is one click away via the **`AR — العربية`** button in the
top-right area (or the sidebar footer). Every page — nav, badges, buttons, empty states,
error messages — follows the active language (`frontend/lib/lang.tsx`).

## Notes & honesty

- **Archive is no longer a project.** The old `legacy/` and pre-HQ code were moved to
  `archive/` with a full explanation (`archive/ARCHIVE.md`). Nothing there runs or is imported.
- Live LLM: Mistral free tier hits 429 often. The `ResilientChatModel` wrapper
  **falls back to deterministic replies** and labels the note in the UI (`llm_note`).
- Real Etsy: fill `ETSY_API_KEY`, `ETSY_ACCESS_TOKEN`, `ETSY_SHOP_ID` in `.env` for real listing creation.
- The product is domain-agnostic — Books Agent was the first department, not the identity of the system.
