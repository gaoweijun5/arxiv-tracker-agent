# ArXiv 论文追踪 Agent

基于 LangChain、LangGraph 和 RAG 技术栈构建的 AI 论文追踪与智能推荐系统。

[English](README.md) | 中文

## 功能特性

- **智能论文发现** - 根据研究兴趣搜索 arXiv，支持自定义日期范围
- **AI 摘要生成** - 使用 DeepSeek 生成论文摘要、关键发现和中文翻译
- **语义推荐** - 基于 DashScope 向量嵌入的论文匹配推荐
- **RAG 问答** - 基于论文内容的上下文感知问答
- **实时进度** - WebSocket 驱动的论文抓取实时进度显示
- **论文管理** - 收藏、标记已读、筛选、删除论文

## 技术栈

| 组件 | 技术 |
|------|------|
| **后端** | Python, FastAPI, LangChain, LangGraph |
| **LLM** | DeepSeek v4 Flash |
| **向量嵌入** | DashScope text-embedding-v4 |
| **向量数据库** | ChromaDB |
| **关系数据库** | SQLite + SQLAlchemy |
| **前端** | React, TypeScript, Tailwind CSS |
| **包管理** | uv (Python), npm (Node) |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### 安装步骤

```bash
# 克隆仓库
git clone git@github.com:gaoweijun5/arxiv-tracker-agent.git
cd arxiv-tracker-agent

# 安装后端依赖
uv venv
source .venv/bin/activate  # macOS/Linux
uv pip install -e .

# 安装前端依赖
cd frontend && npm install && cd ..

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 API 密钥
```

### 环境配置

编辑 `.env` 文件：

```env
# LLM API (DeepSeek)
OPENAI_API_KEY=sk-your-deepseek-key
OPENAI_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash

# 向量嵌入 API (DashScope)
EMBEDDING_API_KEY=sk-your-dashscope-key
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
```

### 启动服务

```bash
# 终端 1：启动后端
uv run uvicorn backend.main:app --reload --port 8000

# 终端 2：启动前端
cd frontend && npm run dev
```

访问 http://localhost:3000

## 使用指南

### 1. 添加研究兴趣

进入 **Interests** 页面，添加你的研究主题、关键词和 arXiv 分类。

### 2. 抓取论文

在 Dashboard 或 Settings 页面点击 **Fetch Papers**：
- 选择要搜索的特定话题
- 选择搜索时间范围（1-30 天）
- 设置每个话题的最大结果数
- 通过 WebSocket 实时查看进度

### 3. 浏览论文

**Papers** 页面以表格形式展示所有论文：
- 按 全部 / 未读 / 已收藏 筛选
- 查看 AI 生成的摘要
- 点击进入详情页阅读全文并提问

### 4. 论文问答

在论文详情页点击 **Chat** 打开问答侧边栏：
- 针对论文内容提问
- AI 基于 RAG 技术回答问题
- 对话历史自动保存

## API 接口

### 论文接口
- `GET /api/v1/papers` - 获取论文列表
- `GET /api/v1/papers/{id}` - 获取论文详情
- `DELETE /api/v1/papers/{id}` - 删除论文
- `PUT /api/v1/papers/{id}/read` - 标记已读
- `PUT /api/v1/papers/{id}/bookmark` - 切换收藏
- `POST /api/v1/papers/search` - 语义搜索

### 兴趣接口
- `GET /api/v1/interests` - 获取兴趣列表
- `POST /api/v1/interests` - 创建兴趣
- `PUT /api/v1/interests/{id}` - 更新兴趣
- `DELETE /api/v1/interests/{id}` - 删除兴趣

### 推荐接口
- `GET /api/v1/recommendations` - 获取推荐列表
- `GET /api/v1/recommendations/today` - 今日推荐
- `POST /api/v1/recommendations/refresh` - 刷新推荐

### 系统接口
- `POST /api/v1/system/fetch` - 抓取论文（支持选项）
- `GET /api/v1/system/stats` - 系统统计
- `GET /api/v1/system/fetch-logs` - 抓取历史

### WebSocket
- `ws://localhost:8000/ws/progress/{task_id}` - 实时进度

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React)                            │
│    Dashboard | Papers | Recommendations | Interests         │
└─────────────────────────┬───────────────────────────────────┘
│
│                    HTTP + WebSocket
│
└─────────────────────────┬───────────────────────────────────┐
│                      后端 (FastAPI)                           │
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

### LangGraph 工作流

```
抓取论文 → 分析论文 → 筛选相关 → 生成推荐 → 保存数据库
```

每个步骤通过 WebSocket 发送进度更新，实现前端实时显示。

## 许可证

MIT
