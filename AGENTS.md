# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

AI-powered arXiv paper tracking and recommendation system with an autonomous LangGraph ReAct agent. Users configure research interests, the agent automatically searches arXiv, analyzes papers with LLM, and saves relevant ones. Papers can be queried via full-text Q&A.

## Commands

```bash
make setup          # One-command install: creates .env, installs backend + frontend deps
make dev            # Start backend (port 8000) + frontend (port 3000) concurrently
make backend        # Backend only
make frontend       # Frontend only
make clean          # Remove all generated files (.venv, node_modules, data/, etc.)

# Backend
uv run uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Lint
cd frontend && npm run lint
```

## Architecture

```
Frontend (React/TS/Vite, port 3000)
    │ HTTP + WebSocket
    ▼
Backend (FastAPI, port 8000)
    ├── api/          REST endpoints under /api/v1 + WebSocket
    ├── agents/       LangGraph ReAct agent (paper_agent) + tools
    ├── services/     Business logic (arxiv, llm, pdf, rag, vector_store)
    ├── models/       SQLAlchemy models (SQLite)
    ├── core/         Config via pydantic-settings + .env
    └── scheduler.py  APScheduler for daily auto-fetch
```

### Key Data Flow

1. **Paper Ingestion**: `paper_agent.py` (ReAct agent) calls tools in `tools.py` → searches arXiv → analyzes with LLM → downloads PDF → saves to SQLite + ChromaDB
2. **Q&A**: `rag_service.py` reads full PDF text (not chunks) → sends to LLM as context
3. **Similar Papers**: vector store semantic search on paper title+abstract embeddings

### Agent Architecture

- **Paper Agent** (`paper_agent.py`): LangGraph `create_react_agent` with 7 tools defined in `tools.py`. The agent autonomously decides tool call order. System prompt strictly limits searches to user-selected interests.
- **QA Agent** (`qa_agent.py`): Legacy StateGraph, not used by the frontend (Q&A goes through `rag_service.py` directly).

Tools communicate task context via `contextvars.ContextVar` (task_id for WebSocket progress, selected_interests for filtering, stats for counting).

### Configuration

All config in `backend/core/config.py` via pydantic-settings, loaded from `.env`. Key vars:
- `OPENAI_API_KEY` (required) — used for LLM (DeepSeek)
- `EMBEDDING_API_KEY` — DashScope embedding API (defaults to DashScope endpoint)
- `LANGSMITH_API_KEY` — optional, for tracing

## Important Patterns

- **Services are singletons** via `get_*()` functions (e.g., `get_vector_store()`, `get_llm_service()`)
- **Async everywhere** — DB is aiosqlite, HTTP is httpx, LLM calls are async. arXiv library is sync, wrapped with `asyncio.to_thread` + 90s timeout
- **Frontend API layer** in `frontend/src/services/api.ts` — all backend calls go through `papersApi`, `conversationsApi`, `systemApi` objects
- **WebSocket progress** — backend sends real-time updates during fetch via `/ws/progress/{task_id}`, frontend `FetchModal` connects on fetch start
- **Error handling in agent tools** — each tool catches exceptions and returns JSON error strings (never raises), so the agent can reason about failures

## arXiv Rate Limiting

The arXiv API aggressively rate limits (HTTP 429). The `search_papers` method retries 3 times with backoff (5s/10s/15s). If fetch returns 0 papers, it's likely rate limiting — wait 10-30 minutes. This is documented in README Troubleshooting.
