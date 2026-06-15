# ArXiv 论文追踪 Agent

> **如果这个项目对你有帮助，请给一个 ⭐ Star！你的支持是我持续改进的动力。**

基于 LangChain、LangGraph StateGraph、混合 RAG 检索与可选 VLM 增强 PDF 解析构建的 AI 论文追踪、智能推荐与论文问答系统。

![项目截图1](./demo/demo1.png)
![项目截图2](./demo/demo2.png)

[English](README.md) | 中文

## 功能特性

- **自主论文 Agent** - 确定性的 LangGraph StateGraph 工作流自动发现、分析和保存论文，支持多重 fallback 策略
- **智能论文发现** - 根据研究兴趣搜索 arXiv，支持自定义日期范围和多种搜索策略
- **Topic Explorer** - 使用自然语言探索新研究方向，通过 WebSocket 实时返回进度，并可将结果论文保存到收藏库
- **AI 摘要生成** - 生成论文摘要、关键发现和中文翻译，支持 OpenAI 兼容接口和 Anthropic 接口
- **语义推荐** - 基于 OpenAI 兼容 Embedding 接口的论文匹配推荐，默认示例使用 DashScope
- **研究报告** - 每次手动或定时抓取后生成持久化 Markdown 研究报告
- **混合检索论文问答** - 手动下载论文 PDF 后，结合语义向量召回、BM25 关键词召回、RRF 重排和全文回退进行问答
- **Docling + VLM Caption** - 使用 Docling 解析 PDF，并可通过 OpenAI 兼容 VLM 为 table/figure 生成 caption 后再切分 chunk
- **实时进度** - WebSocket 驱动的论文抓取实时进度显示
- **论文管理** - 收藏、标记已读、筛选、批量删除论文
- **LangSmith 可观测性** - Agent 决策和 LLM 调用的完整追踪
- **自动 Fallback** - LLM 失败时回退到本地评分；API 超时时指数退避重试
- **周期性清理** - 自动清理超过 30 天、已读且不在收藏夹的旧论文

## 快速开始

> ⚠️ **面向 macOS 本地运行。**

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

`make setup` 会根据 `.env.example` 创建本地 `.env` 文件。请编辑 `.env` 并填入需要的配置。

```env
# === LLM API ===
# 提供商: "openai"（DeepSeek/OpenAI 兼容）或 "anthropic"
LLM_PROVIDER=openai

# OpenAI 兼容接口（DeepSeek、OpenAI 等）
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
# 可选：Fetch Papers Agent 单独使用支持工具调用的模型。
# 如果主模型是 deepseek-reasoner 这类推理模型，建议单独配置该项。
# LLM_AGENT_MODEL=deepseek-v4-flash

# Anthropic 接口 
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# ANTHROPIC_MODEL=claude-sonnet-4-20250514

# === Embedding API ===
# 语义搜索、推荐和相似论文匹配需要配置该项。
# 兼容 OpenAI Embedding API 格式的服务都可以使用（DashScope、DeepSeek、OpenAI 等）。
EMBEDDING_API_KEY=sk-your-embedding-key
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4

# === VLM Caption API ===
# OpenAI 兼容 chat completions 接口，用于给 Docling 解析出的 table/figure 生成 caption。
# 可选；开启 PDF 解析阶段的 table/figure caption。
# VLM_API_KEY=sk-your-vlm-api-key
# VLM_API_ENDPOINT=https://api.openai.com/v1
# VLM_MODEL=gpt-4o-mini
# VLM_IMAGE_SCALE=2.0

# === Optional ===
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=Agent

# === 高级配置（默认值通常即可）
# DATABASE_URL=sqlite+aiosqlite:///./data/arxiv_tracker.db
# CHROMA_PERSIST_DIR=./data/vectors
# ARXIV_MAX_RESULTS=50
# ARXIV_PAGE_SIZE=10
# ARXIV_REQUEST_INTERVAL_SECONDS=3
# ARXIV_MAX_RETRIES=2
# ARXIV_RATE_LIMIT_BACKOFF_SECONDS=60
# ARXIV_REQUEST_TIMEOUT_SECONDS=90
# ARXIV_USER_AGENT="arxiv-tracker-agent/0.1.0 (mailto:your-email@example.com)"
# RAG_CHUNK_TOP_K=8
# RAG_RETRIEVAL_CANDIDATES=20
# RAG_CONFIDENCE_THRESHOLD=0.65
# RAG_RRF_K=60
# DAILY_FETCH_HOUR=8
# DAILY_FETCH_MINUTE=0
```

`ARXIV_USER_AGENT` 建议填写能识别你的应用并包含联系邮箱或项目 URL 的值。默认抓取策略会更保守：arXiv API 和 PDF 请求全局串行执行，请求之间至少间隔 3 秒，搜索分页默认最多 10 条，遇到 403/429 会进入更长的共享退避。

### 本地启动

```bash
make dev
```

同时启动后端（http://localhost:8000）和前端（http://localhost:3000）。项目默认通过 `make` 在本地运行。

其他命令：
- `make backend` - 仅启动后端
- `make frontend` - 仅启动前端
- `make clean` - 清理生成的文件

## 使用指南

### 1. 添加研究兴趣

进入 **Interests** 页面，添加你的研究主题、关键词和 arXiv 分类。

### 2. 探索新主题

在 Dashboard 的 **Explore a Topic** 中可以用自然语言快速探索一个研究方向：
- 输入研究问题或主题描述
- Explorer 会扩展关键词、搜索 arXiv、分析候选论文，并通过 WebSocket 实时返回进度
- 对有价值的论文可以直接保存到你的论文库

### 3. 抓取论文

在 Dashboard 或 Settings 页面点击 **Fetch Papers**：
- 选择要搜索的特定话题
- 选择搜索时间范围（1-30 天）
- 设置每个话题的最大结果数
- Agent 自动搜索、分析、筛选并保存高质量论文的元数据
- 需要论文问答时，在论文详情页手动点击下载按钮
- 每次抓取完成后会生成研究报告，并保存到 **Reports**
- 通过 WebSocket 实时查看进度

### 4. 浏览论文

**Papers** 页面以表格形式展示所有论文：
- 按 全部 / 待读 / 已收藏 筛选
- 按日期或评分排序
- 勾选多篇论文进行批量删除
- 查看 AI 生成的摘要
- 点击进入详情页阅读全文并提问

### 5. 论文问答

在论文详情页点击 **Chat** 打开问答侧边栏：
- 先点击下载按钮，让论文进入 **PDF Ready** 状态
- 针对论文内容提问
- 后端会使用 Docling 解析 PDF，可选使用 VLM 为 table/figure 生成 caption，并生成段落感知的 chunks
- 问答优先使用混合 chunk 检索（语义向量 + BM25 + RRF）；如果检索置信度不足，则回退到由 chunks 重建的全文上下文
- 使用 chunk 级检索时，前端会展示 source chunks 和置信度
- 对话历史自动保存
- 点击垃圾桶图标清空聊天记录

## 常见问题

**Fetch 搜不到论文或返回失败**

通常是 arXiv API 限流（HTTP 429）导致的。频繁测试后，建议等待 10-30 分钟再试。系统会串行化 arXiv 请求，请求间至少间隔 3 秒，并在遇到 403/429 后进入退避。

**Fetch 报错 `'str' object has no attribute 'model_dump'`**

通常是 OpenAI-compatible 接口在 Agent 工具调用阶段不兼容导致的。请给抓取 Agent 使用支持 tool calling 的聊天模型，例如 `LLM_AGENT_MODEL=deepseek-v4-flash`。后端检测到这类 provider 工具调用错误时，也会自动回退到顺序执行的兼容抓取流程。

**问答需要下载 PDF**

论文问答采用本地优先策略。请先在论文详情页点击下载按钮；后端会下载 PDF、使用 Docling 解析、生成 chunks，并同步到 SQLite FTS5 和 ChromaDB。

**问答中没有 table/figure caption**

配置 `VLM_API_KEY`、`VLM_API_ENDPOINT` 和 `VLM_MODEL` 后，即可启用 OpenAI 兼容的 table/figure caption。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React)                            │
│ Dashboard | Topic Explorer | Papers | Reports | Settings    │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP + WebSocket
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      后端 (FastAPI)                           │
│ Papers | Conversations | Reports | Explore | System | WS    │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  LangGraph    │ │   Services    │ │   Storage     │
│               │ │               │ │               │
│ - Paper Agent │ │ - arXiv API   │ │ - SQLite      │
│ (StateGraph)  │ │ - LLM API     │ │ - FTS5 chunks │
│ - Topic       │ │ - Docling PDF │ │ - ChromaDB    │
│   Explorer    │ │ - VLM Caption │ │ - 本地 PDF    │
│               │ │ - Hybrid RAG  │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  LangSmith  │
                   │   (追踪)    │
                   └─────────────┘
```

### PDF 与 RAG 问答链路

论文问答默认使用本地混合检索链路：

```
下载 PDF
  ▼
Docling 解析
  ▼
可选 VLM 为 table/figure 生成 caption
  ▼
段落感知 chunks
  ▼
SQLite FTS5 + ChromaDB
  ▼
语义向量召回 + BM25 关键词召回
  ▼
RRF 重排 + 置信度判断
  ▼
基于 source chunks 回答，或回退到全文上下文
```

如果配置了 VLM caption，table 和 figure 的 caption 会在 chunk 前回填到解析出的文档中，使图表语义也能参与检索。

### Paper Agent（StateGraph 工作流）

Paper Agent 使用 LangGraph 的 `StateGraph` 实现确定性论文发现工作流，支持自动 fallback 机制：

```
用户: "Fetch Papers"
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│              StateGraph 工作流（确定性流程）                    │
│                                                              │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────┐ │
│  │ 加载上下文   │───▶│ 构建查询计划     │───▶│ 搜索循环   │ │
│  │              │    │                  │    │            │ │
│  │ • 研究兴趣   │    │ • 主搜索策略     │    │ • 执行搜索 │ │
│  │ • 用户反馈   │    │ • 仅分类搜索     │    │ • Fallback │ │
│  └──────────────┘    │ • 仅关键词搜索   │    │   策略     │ │
│                      │ • 扩展时间范围   │    └─────┬──────┘ │
│                      └──────────────────┘          │        │
│                                                    ▼        │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────┐ │
│  │ 保存循环     │◀───│ LLM 分析         │◀───│ 本地评分   │ │
│  │              │    │                  │    │            │ │
│  │ • 保存到 DB  │    │ • 生成摘要       │    │ • 关键词   │ │
│  │ • 更新向量   │    │ • 相关性检查     │    │   匹配     │ │
│  └──────┬───────┘    │ • LLM 失败时     │    │ • 分类     │ │
│         │            │   自动 Fallback  │    │   匹配     │ │
│         ▼            └──────────────────┘    └────────────┘ │
│  ┌──────────────┐    ┌──────────────────┐                    │
│  │ 完成         │───▶│ 生成研究报告     │                    │
│  │              │    │                  │                    │
│  │ • 统计信息   │    │ • LLM 生成       │                    │
│  │ • 错误记录   │    │ • Fallback 模板  │                    │
│  │ • Fallback   │    │                  │                    │
│  └──────────────┘    └──────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

**核心特性：**
- **确定性流程** - 预定义节点序列，执行更稳定
- **多重搜索策略** - 每个研究兴趣生成 4-6 次不同参数的搜索尝试
- **本地评分** - 在昂贵的 LLM 分析前进行快速关键词/分类匹配
- **自动 Fallback** - LLM 失败回退到本地评分；超时自动重试
- **速率限制处理** - 遇到 429/403 响应时自动退避

## 许可证

MIT
