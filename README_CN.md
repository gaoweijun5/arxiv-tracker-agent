# ArXiv 论文追踪 Agent

> **如果这个项目对你有帮助，请给一个 ⭐ Star！你的支持是我持续改进的动力。**

基于 LangChain、LangGraph ReAct Agent 构建的 AI 论文追踪与智能推荐系统。

https://github.com/user-attachments/assets/880cb912-5e25-4a0f-b684-710d7716dbaf

[English](README.md) | 中文

## 功能特性

- **自主论文 Agent** - ReAct Agent 自主决定搜索策略、分析论文、保存最优结果
- **智能论文发现** - 根据研究兴趣搜索 arXiv，支持自定义日期范围
- **AI 摘要生成** - 生成论文摘要、关键发现和中文翻译，支持 OpenAI 兼容接口和 Anthropic 接口
- **语义推荐** - 基于 DashScope 向量嵌入的论文匹配推荐
- **研究报告** - 每次手动或定时抓取后生成持久化 Markdown 研究报告
- **全文问答** - 手动下载论文 PDF 后，基于完整 PDF 内容进行问答
- **实时进度** - WebSocket 驱动的论文抓取实时进度显示
- **论文管理** - 收藏、标记已读、筛选、批量删除论文
- **LangSmith 可观测性** - Agent 决策和 LLM 调用的完整追踪

## 快速开始

> ⚠️ **本项目仅支持 macOS 系统，不支持 Windows 和 Linux。**

### 环境要求

- macOS
- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### 本地安装

```bash
git clone git@github.com:gaoweijun5/arxiv-tracker-agent.git
cd arxiv-tracker-agent
make setup
```

自动创建 `.env`、安装所有依赖、创建数据目录。

### 配置

`make setup` 会根据 `.env.example` 创建本地 `.env` 文件。请编辑 `.env` 并填入需要的配置，不要提交 `.env`。

```env
# === LLM API ===
# 提供商: "openai" 或 "anthropic"
LLM_PROVIDER=openai

# OpenAI 兼容接口
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_API_BASE=your-api-base-here
LLM_MODEL=deepseek-v4-flash
# 可选：Fetch Papers Agent 单独使用支持工具调用的模型
# LLM_AGENT_MODEL=deepseek-v4-flash

# Anthropic 接口 
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# ANTHROPIC_MODEL=claude-sonnet-4-20250514

# === Embedding API ===
# 语义搜索、推荐和相似论文匹配需要配置该项。
# 兼容 OpenAI Embedding API 格式的服务都可以使用。
EMBEDDING_API_KEY=sk-your-embedding-key
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4

# === Optional ===
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=Agent

# === Advanced
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

`ARXIV_USER_AGENT` 建议填写能识别你的应用并包含联系邮箱或项目 URL 的值。默认抓取策略会更保守：arXiv API 和 PDF 请求全局串行执行，请求之间至少间隔 3 秒，搜索分页默认最多 10 条，遇到 403/429 会进入更长的共享退避。

### 本地启动

```bash
make dev
```

同时启动后端（http://localhost:8000）和前端（http://localhost:3000）。项目默认通过 `make` 在本地运行，不需要 Docker。

其他命令：
- `make backend` - 仅启动后端
- `make frontend` - 仅启动前端
- `make clean` - 清理生成的文件

## 使用指南

### 1. 添加研究兴趣

进入 **Interests** 页面，添加你的研究主题、关键词和 arXiv 分类。

### 2. 抓取论文

在 Dashboard 或 Settings 页面点击 **Fetch Papers**：
- 选择要搜索的特定话题
- 选择搜索时间范围（1-30 天）
- 设置每个话题的最大结果数
- Agent 自动搜索、分析、筛选并保存高质量论文的元数据
- 抓取阶段不会下载 PDF；需要全文问答时，在论文详情页手动点击下载按钮
- 每次抓取完成后会生成研究报告，并保存到 **Reports**
- 通过 WebSocket 实时查看进度

### 3. 浏览论文

**Papers** 页面以表格形式展示所有论文：
- 按 全部 / 未读 / 已收藏 筛选
- 按日期或评分排序
- 勾选多篇论文进行批量删除
- 查看 AI 生成的摘要
- 点击进入详情页阅读全文并提问

### 4. 论文问答

在论文详情页点击 **Chat** 打开问答侧边栏：
- 如果论文还不是 **PDF Ready**，请先点击下载按钮
- 针对论文内容提问
- AI 读取完整 PDF 全文进行回答
- 对话历史自动保存
- 点击垃圾桶图标清空聊天记录

## 常见问题

**Fetch 搜不到论文或返回失败**

通常是 arXiv API 限流（HTTP 429）导致的，不是系统 bug。arXiv 对同一 IP 的请求频率有限制，如果频繁测试，需等待 10-30 分钟后再试。系统会串行化 arXiv 请求，请求间至少间隔 3 秒，并在遇到 403/429 后进入退避。

**Fetch 报错 `'str' object has no attribute 'model_dump'`**

通常是 OpenAI-compatible 接口在 Agent 工具调用阶段不兼容导致的。请给抓取 Agent 使用支持 tool calling 的聊天模型，例如 `LLM_AGENT_MODEL=deepseek-v4-flash`，不要让抓取 Agent 直接使用 `deepseek-reasoner` 这类推理模型。后端检测到这类 provider 工具调用错误时，也会自动回退到顺序执行的兼容抓取流程。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React)                            │
│    Dashboard | Papers | Recommendations | Interests         │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP + WebSocket
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      后端 (FastAPI)                           │
│    Papers API | Interests API | System API | WebSocket      │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  LangGraph    │ │   Services    │ │   Storage     │
│               │ │               │ │               │
│ - Paper Agent │ │ - arXiv API   │ │ - SQLite      │
│ (ReAct)       │ │ - LLM API    │ │ - ChromaDB    │
│               │ │ - RAG 问答    │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  LangSmith  │
                   │   (追踪)    │
                   └─────────────┘
```

### Paper Agent（ReAct 模式）

Paper Agent 使用 LangGraph 的 `create_react_agent` 自主发现、分析和保存论文：

```
用户: "帮我找匹配研究兴趣的论文"
  │
  ▼
┌─────────────────────────────────────────────┐
│          ReAct 循环（LLM 驱动）               │
│                                              │
│  1. get_user_interests() → 了解研究主题       │
│  2. get_user_feedback_summary() → 学习偏好   │
│  3. search_arxiv() → 搜索论文                │
│  4. check_paper_exists() → 跳过已存在论文     │
│  5. check_relevance() → 快速筛选             │
│  6. analyze_paper() → 完整分析               │
│  7. save_paper() → 保存最优论文元数据        │
│                                              │
│  LLM 自主决定工具调用顺序                     │
│  根据结果调整策略（反思）                      │
└─────────────────────────────────────────────┘
```

## 许可证

MIT
