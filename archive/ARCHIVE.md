# Archive — KidBook Agent 1.0 (reference only)

This directory is the historical codebase from before the project became **AI Business HQ**.
Nothing here is built, imported, tested or deployed anymore — it is kept for reading.

## What lives where now

| Before (this archive) | Now (root) |
| --- | --- |
| `kidbook/` package (domains, engine, tools, Streamlit dashboard, CLI) | `agents/` (LangGraph CEO + departments) + `backend/` (FastAPI) + `frontend/` (Next.js) |
| `app.py` Streamlit “Kid Book Agent” | Next.js pages under `frontend/app/*` |
| `main.py` CLI | `backend/app/` REST endpoints + `frontend/` |
| `books/`, `reports/`, `data/` outputs | `storage/books`, `storage/reports`, root `data/hq.db` |
| Amiri font at `fonts/` | kept at root — still used by `agents/capabilities/pdf.py` |

## Kernel facts

- AI CEO = LangGraph graph (`agents/ceo/graph.py`) — not a chatbot with a system prompt.
- Departments registry = `agents/registry.py` — add a spec, everything picks it up.
- Capabilities registry (`agents/capabilities/__init__.py`) — one implementation shared by every department.
- Human approval gate = `approvals` table + UI — no external effect without your sign-off.

Do not run or import anything from this folder; everything you need is at the repository root.
