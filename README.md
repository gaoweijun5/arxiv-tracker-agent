# ArXiv Tracker Agent

> **If you find this project helpful, please give it a ⭐ Star! Your support is my motivation to keep improving.**

AI-powered arXiv paper tracking and recommendation system with an autonomous LangGraph ReAct agent.

https://github.com/user-attachments/assets/880cb912-5e25-4a0f-b684-710d7716dbaf

English | [中文](README_CN.md)

## Features

- **Autonomous Paper Agent** - ReAct agent that independently decides search strategy, analyzes papers, and saves the best ones
- **Smart Paper Discovery** - Search arXiv based on your research interests with configurable date range
- **AI Summarization** - Generate summaries, key findings, and Chinese translations using DeepSeek
- **Semantic Recommendations** - Vector-based paper matching using DashScope embeddings
- **Full-text Q&A** - Manually download a paper PDF, then ask questions with full PDF content as context
- **Real-time Progress** - WebSocket-powered live updates during paper fetching
- **Paper Management** - Bookmark, mark as read, filter, batch delete papers
- **LangSmith Observability** - Full tracing of agent decisions and LLM calls

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Local Setup

```bash
git clone git@github.com:gaoweijun5/arxiv-tracker-agent.git
cd arxiv-tracker-agent
make setup
```

This will create `.env`, install all dependencies, and create data directories.

### Configuration

```env
# === LLM API ===
OPENAI_API_KEY=sk-your-api-key-here

# Set your Model
OPENAI_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash

# === Embedding API ===
# Any OpenAI-compatible embedding API works.
EMBEDDING_API_KEY=sk-your-embedding-key
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4

# === Optional ===
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=Agent

# === Advanced (defaults are fine) ===
# DATABASE_URL=sqlite+aiosqlite:///./data/arxiv_tracker.db
# CHROMA_PERSIST_DIR=./data/vectors
# ARXIV_MAX_RESULTS=50
# ARXIV_PAGE_SIZE=10
# ARXIV_REQUEST_INTERVAL_SECONDS=3
# ARXIV_MAX_RETRIES=2
# ARXIV_RATE_LIMIT_BACKOFF_SECONDS=60
# ARXIV_REQUEST_TIMEOUT_SECONDS=90
# ARXIV_USER_AGENT="arxiv-tracker-agent/0.1.0 (mailto:your-email@example.com)"
# DAILY_FETCH_HOUR=8
# DAILY_FETCH_MINUTE=0
```

`ARXIV_USER_AGENT` should identify your app and include a contact email or project URL. The default crawler is conservative: arXiv API and PDF requests are serialized, spaced at least 3 seconds apart, search pages are capped at 10 records, and 403/429 responses trigger a longer shared backoff.

### Local Run

```bash
make dev
```

This starts both backend (http://localhost:8000) and frontend (http://localhost:3000) simultaneously. The project is intended to run locally through `make`; Docker is not required.

Other commands:
- `make backend` - Start backend only
- `make frontend` - Start frontend only
- `make clean` - Clean generated files

## Usage

### 1. Add Research Interests

Go to **Interests** page and add your research topics with keywords and arXiv categories.

### 2. Fetch Papers

Click **Fetch Papers** on Dashboard or Settings page:
- Select specific topics to search
- Choose search period (1-30 days)
- Set max results per topic
- The autonomous agent will search, analyze, and save paper metadata automatically
- PDFs are not downloaded during fetch; use the download button on a paper detail page when you need full-text Q&A
- Watch real-time progress via WebSocket

### 3. Browse Papers

**Papers** page shows all fetched papers in a table:
- Filter by All / Unread / Bookmarked
- Sort by Date or Score
- Select multiple papers for batch delete
- View AI-generated summaries
- Click to read full details and ask questions

### 4. Paper Q&A

On paper detail page, click **Chat** to open the Q&A sidebar:
- Click the download button first if the paper is not marked **PDF Ready**
- Ask questions about the paper
- AI reads the full PDF and answers based on complete content
- Conversation history is saved
- Clear chat history with the trash icon

## Troubleshooting

**Fetch returns 0 papers or fails**

This is usually caused by arXiv API rate limiting (HTTP 429), not a system bug. arXiv limits the number of requests from the same IP. If you've been testing frequently, wait 10-30 minutes before trying again. The system serializes arXiv traffic, waits at least 3 seconds between requests, and backs off after 403/429 responses.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                          │
│    Dashboard | Papers | Recommendations | Interests         │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP + WebSocket
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                          │
│    Papers API | Interests API | System API | WebSocket      │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  LangGraph    │ │   Services    │ │   Storage     │
│               │ │               │ │               │
│ - Paper Agent │ │ - arXiv API   │ │ - SQLite      │
│ (ReAct)       │ │ - DeepSeek    │ │ - ChromaDB    │
│               │ │ - RAG Q&A     │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  LangSmith  │
                   │  (Tracing)  │
                   └─────────────┘
```

### Paper Agent (ReAct)

The Paper Agent uses LangGraph's `create_react_agent` to autonomously discover, analyze, and save papers:

```
User: "Find papers matching my interests"
  │
  ▼
┌─────────────────────────────────────────────┐
│            ReAct Loop (LLM-driven)           │
│                                              │
│  1. get_user_interests() → understand topics │
│  2. get_user_feedback_summary() → learn prefs│
│  3. search_arxiv() → find papers             │
│  4. check_paper_exists() → skip duplicates   │
│  5. check_relevance() → quick filter         │
│  6. analyze_paper() → full analysis          │
│  7. save_paper() → save best metadata        │
│                                              │
│  LLM decides tool order and adjusts strategy │
│  based on results (reflection)               │
└─────────────────────────────────────────────┘
```

## API Endpoints

<details>
<summary>Click to expand</summary>

### Papers
- `GET /api/v1/papers` - List papers (supports filtering and sorting)
- `GET /api/v1/papers/{id}` - Get paper details
- `DELETE /api/v1/papers/{id}` - Delete paper
- `POST /api/v1/papers/batch-delete` - Batch delete papers by IDs
- `PUT /api/v1/papers/{id}/read` - Mark as read
- `PUT /api/v1/papers/{id}/bookmark` - Toggle bookmark
- `POST /api/v1/papers/{id}/download` - Download PDF for Q&A
- `POST /api/v1/papers/search` - Semantic search

### Conversations
- `POST /api/v1/conversations/ask` - Ask a question about a paper
- `GET /api/v1/conversations/{paper_id}` - Get conversation history
- `DELETE /api/v1/conversations/paper/{paper_id}` - Clear chat history

### Interests
- `GET /api/v1/interests` - List interests
- `POST /api/v1/interests` - Create interest
- `PUT /api/v1/interests/{id}` - Update interest
- `DELETE /api/v1/interests/{id}` - Delete interest

### Recommendations
- `GET /api/v1/recommendations` - List recommendations
- `GET /api/v1/recommendations/today` - Today's recommendations
- `POST /api/v1/recommendations/refresh` - Refresh recommendations

### System
- `POST /api/v1/system/fetch` - Fetch papers with options
- `GET /api/v1/system/stats` - System statistics
- `GET /api/v1/system/fetch-logs` - Fetch history (with source: manual/auto)
- `GET /api/v1/system/scheduler` - Get scheduler config
- `PUT /api/v1/system/scheduler` - Update scheduler config

### WebSocket
- `ws://localhost:8000/ws/progress/{task_id}` - Real-time progress

</details>

## License

MIT
