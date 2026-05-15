# ArXiv Tracker Agent

AI-powered arXiv paper tracking and recommendation system built with LangChain, LangGraph, and RAG.

## Features

- **Smart Paper Discovery** - Search arXiv based on your research interests with configurable date range
- **AI Summarization** - Generate summaries, key findings, and Chinese translations using DeepSeek
- **Semantic Recommendations** - Vector-based paper matching using DashScope embeddings
- **RAG Q&A** - Ask questions about papers with context-aware answers
- **Real-time Progress** - WebSocket-powered live updates during paper fetching
- **Paper Management** - Bookmark, mark as read, filter, and delete papers

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python, FastAPI, LangChain, LangGraph |
| **LLM** | DeepSeek v4 Flash |
| **Embedding** | DashScope text-embedding-v4 |
| **Vector Store** | ChromaDB |
| **Database** | SQLite + SQLAlchemy |
| **Frontend** | React, TypeScript, Tailwind CSS |
| **Package Manager** | uv (Python), npm (Node) |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Installation

```bash
# Clone repository
git clone git@github.com:gaoweijun5/arxiv-tracker-agent.git
cd arxiv-tracker-agent

# Setup backend
uv venv
source .venv/bin/activate  # macOS/Linux
uv pip install -e .

# Setup frontend
cd frontend && npm install && cd ..

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` file:

```env
# LLM API (DeepSeek)
OPENAI_API_KEY=sk-your-deepseek-key
OPENAI_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash

# Embedding API (DashScope)
EMBEDDING_API_KEY=sk-your-dashscope-key
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
```

### Run

```bash
# Terminal 1: Backend
uv run uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

Access at http://localhost:3000

## Usage

### 1. Add Research Interests

Go to **Interests** page and add your research topics with keywords and arXiv categories.

### 2. Fetch Papers

Click **Fetch Papers** on Dashboard or Settings page:
- Select specific topics to search
- Choose search period (1-30 days)
- Set max results per topic
- Watch real-time progress via WebSocket

### 3. Browse Papers

**Papers** page shows all fetched papers in a table:
- Filter by All / Unread / Bookmarked
- View AI-generated summaries
- Click to read full details and ask questions

### 4. Paper Q&A

On paper detail page, click **Chat** to open the Q&A sidebar:
- Ask questions about the paper
- AI answers based on paper content using RAG
- Conversation history is saved

## API Endpoints

### Papers
- `GET /api/v1/papers` - List papers
- `GET /api/v1/papers/{id}` - Get paper details
- `DELETE /api/v1/papers/{id}` - Delete paper
- `PUT /api/v1/papers/{id}/read` - Mark as read
- `PUT /api/v1/papers/{id}/bookmark` - Toggle bookmark
- `POST /api/v1/papers/search` - Semantic search

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
- `GET /api/v1/system/fetch-logs` - Fetch history

### WebSocket
- `ws://localhost:8000/ws/progress/{task_id}` - Real-time progress

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
│  LangGraph    │ │   Services    │ │   Database    │
│               │ │               │ │               │
│ - Paper Agent │ │ - arXiv API   │ │ - SQLite      │
│ - QA Agent    │ │ - DeepSeek    │ │ - ChromaDB    │
│               │ │ - DashScope   │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
```

### LangGraph Workflow

```
Fetch Papers → Analyze Papers → Filter Relevant → Generate Recommendations → Save to Database
```

Each step sends progress updates via WebSocket for real-time UI updates.

## License

MIT
