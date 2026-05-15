# ArXiv Tracker Agent

<div align="center">

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3+-FF6B6B.svg)](https://langchain.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://reactjs.org/)

**AI驱动的arXiv论文追踪与智能推荐系统**

基于 LangChain、LangGraph 和 RAG 技术栈构建的完整Agent系统

[功能特性](#功能特性) • [快速开始](#快速开始) • [使用指南](#使用指南) • [API文档](#api文档) • [架构设计](#架构设计)

</div>

---

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
  - [环境要求](#环境要求)
  - [安装步骤](#安装步骤)
  - [配置说明](#配置说明)
  - [启动应用](#启动应用)
- [使用指南](#使用指南)
  - [配置研究兴趣](#配置研究兴趣)
  - [获取论文推荐](#获取论文推荐)
  - [浏览和阅读论文](#浏览和阅读论文)
  - [论文问答对话](#论文问答对话)
  - [每日研究摘要](#每日研究摘要)
- [API文档](#api文档)
- [架构设计](#架构设计)
  - [LangGraph工作流](#langgraph工作流)
  - [RAG系统设计](#rag系统设计)
  - [数据模型](#数据模型)
- [开发指南](#开发指南)
- [部署指南](#部署指南)
- [故障排除](#故障排除)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 项目简介

ArXiv Tracker Agent 是一个基于大语言模型的智能论文追踪系统。它能够：

1. **自动追踪** - 根据你的研究兴趣，每天自动从arXiv抓取最新论文
2. **智能筛选** - 使用AI分析论文内容，筛选出与你研究相关的论文
3. **深度摘要** - 自动生成论文摘要、关键发现和中文翻译
4. **语义推荐** - 基于向量相似度的个性化论文推荐
5. **智能问答** - 使用RAG技术，可以针对论文内容进行深入对话

### 适用场景

- 研究人员需要追踪特定领域的最新进展
- 研究生希望高效筛选和阅读大量论文
- 团队需要共享和讨论相关研究论文
- 任何人希望保持对学术前沿的了解

---

## 功能特性

### 核心功能

| 功能 | 描述 |
|------|------|
| 🔍 **智能论文发现** | 基于用户定义的研究兴趣，自动搜索arXiv上的相关论文 |
| 📝 **AI摘要生成** | 使用GPT-4生成论文摘要、关键发现和方法论总结 |
| 🎯 **语义匹配推荐** | 使用ChromaDB向量存储进行语义相似度匹配 |
| 💬 **RAG论文问答** | 基于论文全文的检索增强生成问答系统 |
| 📰 **每日研究摘要** | 报纸风格的每日研究论文摘要 |
| ⏰ **定时自动抓取** | 每天定时自动获取和处理新论文 |
| 🔖 **论文收藏管理** | 收藏、标记已读、筛选未读论文 |
| 🌐 **中英双语支持** | 支持英文和中文摘要 |

### 特色亮点

- **完整的Agent架构**: 使用LangGraph构建完整的工作流，包含多个智能节点
- **RAG检索增强**: 基于论文全文的向量检索，提供精准的问答上下文
- **可解释的推荐**: 每条推荐都附带推荐原因和匹配度评分
- **现代化UI**: 响应式设计，支持移动端访问
- **本地优先**: 数据存储在本地，保护隐私

---

## 技术栈

### 后端技术

| 技术 | 用途 | 版本 |
|------|------|------|
| **Python** | 主要编程语言 | 3.11+ |
| **FastAPI** | Web框架 | 0.115+ |
| **LangChain** | LLM应用框架 | 0.3+ |
| **LangGraph** | Agent工作流引擎 | 0.2+ |
| **ChromaDB** | 向量数据库 | 0.5+ |
| **SQLAlchemy** | ORM框架 | 2.0+ |
| **sentence-transformers** | 文本嵌入模型 | 3.0+ |
| **PyMuPDF** | PDF处理 | 1.24+ |
| **APScheduler** | 任务调度 | 3.10+ |
| **uv** | 包管理器 | 0.11+ |

### 前端技术

| 技术 | 用途 | 版本 |
|------|------|------|
| **React** | UI框架 | 18+ |
| **TypeScript** | 类型安全 | 5.5+ |
| **Tailwind CSS** | 样式框架 | 3.4+ |
| **Vite** | 构建工具 | 5.4+ |
| **Axios** | HTTP客户端 | 1.7+ |
| **React Router** | 路由管理 | 6.26+ |
| **Lucide React** | 图标库 | 0.441+ |
| **react-markdown** | Markdown渲染 | 9.0+ |

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React + TypeScript)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Dashboard │ │  Papers  │ │ Recommend│ │ Interests│ │ Settings │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP/REST
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ /papers  │ │/interests│ │  /recommend│ │/conversat│ │ /system  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  LangGraph    │      │  LangChain    │      │   Services    │
│   Agents      │      │   Chains      │      │               │
│               │      │               │      │  - ArXiv API  │
│ - Paper Agent │      │ - Summary     │      │  - PDF Parser │
│ - QA Agent    │      │ - Relevance   │      │  - Vector DB  │
│               │      │ - Q&A         │      │  - Scheduler  │
└───────────────┘      └───────────────┘      └───────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Data Layer                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   SQLite     │  │   ChromaDB   │  │  PDF Files   │              │
│  │  (Metadata)  │  │  (Vectors)   │  │  (Papers)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### LangGraph Agent工作流

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Paper Processing Workflow                         │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │  Fetch   │───▶│ Analyze  │───▶│  Filter  │───▶│Recommend │      │
│  │  Papers  │    │  Papers  │    │ Relevant │    │  Papers  │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │                                               │             │
│       │              ┌──────────┐    ┌──────────┐     │             │
│       └──────────────│  Create  │◀───│   Save   │◀────┘             │
│                      │  Digest  │    │   to DB  │                   │
│                      └──────────┘    └──────────┘                   │
│                            │                                        │
│                            ▼                                        │
│                       ┌──────────┐                                  │
│                       │   END    │                                  │
│                       └──────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### RAG问答流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG Q&A Pipeline                                  │
│                                                                     │
│  User Question                                                      │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Retrieve │───▶│  Build   │───▶│ Generate │───▶│   Save   │      │
│  │ Context  │    │  Prompt  │    │ Response │    │ History  │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   ChromaDB Vector Store                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │  │
│  │  │ Chunk 1  │  │ Chunk 2  │  │ Chunk 3  │  │  ...     │    │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- **Python**: 3.11 或更高版本
- **Node.js**: 18 或更高版本
- **uv**: Python包管理器（[安装指南](https://docs.astral.sh/uv/getting-started/installation/)）
- **OpenAI API Key**: 用于LLM和Embedding模型

### 安装步骤

#### 1. 克隆项目

```bash
git clone <repository-url>
cd arxiv-tracker-agent
```

#### 2. 安装uv（如果尚未安装）

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 3. 设置后端环境

```bash
# 创建虚拟环境
uv venv

# 激活虚拟环境
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 安装依赖
uv pip install -e .
```

#### 4. 设置前端环境

```bash
cd frontend
npm install
cd ..
```

#### 5. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件
# macOS
open -e .env
# Linux
nano .env
# Windows
notepad .env
```

### 配置说明

编辑 `.env` 文件，配置以下参数：

```env
# ========== 必需配置 ==========

# OpenAI API密钥（必需）
OPENAI_API_KEY=sk-your-api-key-here

# ========== 可选配置 ==========

# 数据库URL（默认使用SQLite）
DATABASE_URL=sqlite+aiosqlite:///./data/arxiv_tracker.db

# ChromaDB向量存储目录
CHROMA_PERSIST_DIR=./data/vectors

# 嵌入模型（用于语义搜索）
EMBEDDING_MODEL=all-MiniLM-L6-v2

# LLM模型（用于摘要和问答）
LLM_MODEL=gpt-4o-mini

# LLM温度参数（0-1，越低越确定）
LLM_TEMPERATURE=0.3

# arXiv搜索类别（逗号分隔）
ARXIV_CATEGORIES=cs.AI,cs.CL,cs.CV,cs.LG

# 每次搜索最大结果数
ARXIV_MAX_RESULTS=50

# 每日自动抓取时间（24小时制）
DAILY_FETCH_HOUR=8
DAILY_FETCH_MINUTE=0

# 调试模式
DEBUG=true
```

#### arXiv类别说明

| 类别 | 描述 |
|------|------|
| `cs.AI` | 人工智能 |
| `cs.CL` | 计算语言学（NLP） |
| `cs.CV` | 计算机视觉 |
| `cs.LG` | 机器学习 |
| `cs.MA` | 多智能体系统 |
| `cs.NE` | 神经网络与进化计算 |
| `stat.ML` | 统计机器学习 |
| `cs.IR` | 信息检索 |
| `cs.RO` | 机器人学 |

### 启动应用

#### 方式一：使用启动脚本（推荐）

```bash
# 确保脚本有执行权限
chmod +x start.sh

# 启动应用
./start.sh
```

#### 方式二：手动启动

```bash
# 终端1：启动后端
uv run uvicorn backend.main:app --reload --port 8000

# 终端2：启动前端
cd frontend
npm run dev
```

#### 方式三：使用Docker

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 访问应用

启动成功后，访问以下地址：

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端应用** | http://localhost:3000 | 主要用户界面 |
| **后端API** | http://localhost:8000 | API服务 |
| **API文档** | http://localhost:8000/docs | Swagger交互式文档 |
| **ReDoc文档** | http://localhost:8000/redoc | ReDoc格式文档 |

---

## 使用指南

### 配置研究兴趣

1. **访问兴趣页面**
   - 点击左侧导航栏的 "Interests"
   - 或访问 http://localhost:3000/interests

2. **添加新兴趣**
   - 点击 "Add Interest" 按钮
   - 填写以下信息：
     - **Topic**: 研究主题（必填），如 "Large Language Models"
     - **Description**: 详细描述（可选）
     - **Keywords**: 关键词（逗号分隔），如 "transformer, attention, fine-tuning"
     - **Categories**: arXiv类别（多选）
     - **Weight**: 重要性权重（0.1-2.0）

3. **示例配置**

   ```
   Topic: Large Language Models
   Description: 研究大型语言模型的训练、优化和应用
   Keywords: LLM, transformer, GPT, instruction tuning, RLHF
   Categories: cs.CL, cs.AI
   Weight: 1.5
   ```

4. **管理兴趣**
   - 编辑：点击兴趣卡片上的编辑图标
   - 删除：点击删除图标
   - 启用/禁用：通过编辑切换状态

### 获取论文推荐

#### 自动推荐

系统每天会在配置的时间（默认早上8点）自动：
1. 根据你的兴趣搜索arXiv
2. 分析和筛选论文
3. 生成推荐和摘要
4. 保存到数据库

#### 手动获取

1. **通过Dashboard**
   - 访问 http://localhost:3000
   - 点击 "Refresh Papers" 按钮
   - 等待处理完成

2. **通过设置页面**
   - 访问 http://localhost:3000/settings
   - 点击 "Fetch Papers Now" 按钮

3. **通过API**
   ```bash
   curl -X POST http://localhost:8000/api/v1/recommendations/refresh
   ```

### 浏览和阅读论文

#### 论文列表

- 访问 http://localhost:3000/papers
- 使用筛选器：
  - **All**: 显示所有论文
  - **Unread**: 只显示未读论文
  - **Bookmarked**: 只显示收藏论文

#### 论文详情

点击任意论文进入详情页，可以看到：

1. **基本信息**
   - 标题、作者、发表日期
   - arXiv类别标签
   - PDF链接

2. **AI生成内容**
   - 英文摘要
   - 中文摘要
   - 关键发现列表

3. **操作按钮**
   - 收藏/取消收藏
   - 查看PDF原文
   - 打开问答对话

#### 收藏管理

- 点击书签图标收藏论文
- 收藏的论文不会被自动清理
- 可以通过筛选器快速找到收藏论文

### 论文问答对话

1. **打开对话**
   - 在论文详情页点击 "Chat" 按钮
   - 右侧会打开对话面板

2. **提问**
   - 输入你的问题
   - 按Enter或点击发送按钮
   - AI会基于论文内容回答

3. **对话示例**

   ```
   User: What is the main contribution of this paper?
   AI: The main contribution is...

   User: How does this compare to previous work?
   AI: Compared to previous work, this paper...

   User: What are the limitations mentioned?
   AI: The authors mention several limitations...
   ```

4. **技术原理**
   - 使用RAG（检索增强生成）技术
   - 从论文全文中检索相关段落
   - 基于检索到的上下文生成回答
   - 保证回答的准确性和可追溯性

### 每日研究摘要

1. **查看摘要**
   - 访问 http://localhost:3000/recommendations
   - 页面顶部显示每日研究摘要

2. **摘要内容**
   - 报纸风格的论文概述
   - 每篇论文的简要介绍
   - 为什么这篇论文重要

3. **示例摘要**

   ```
   📰 Daily Research Digest - May 15, 2026

   🔬 New Breakthrough in LLM Reasoning
   Researchers from Stanford present a novel approach to improving
   reasoning capabilities in large language models...

   🤖 Efficient Fine-tuning Method Proposed
   A team from Google Research demonstrates a new parameter-efficient
   fine-tuning technique that reduces memory usage by 60%...
   ```

---

## API文档

### 认证

当前版本不需要认证（本地使用）。生产环境建议添加认证。

### 响应格式

所有API响应使用JSON格式：

```json
{
  "data": { ... },
  "message": "Success",
  "status": 200
}
```

### 错误响应

```json
{
  "detail": "Error message",
  "status": 400
}
```

### Papers API

#### 获取论文列表

```http
GET /api/v1/papers
```

**参数：**

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量（1-100） |
| `category` | string | - | arXiv类别筛选 |
| `is_read` | bool | - | 是否已读 |
| `is_bookmarked` | bool | - | 是否收藏 |
| `sort_by` | string | created_at | 排序字段 |
| `sort_order` | string | desc | 排序顺序 |

**响应：**

```json
{
  "papers": [
    {
      "id": 1,
      "arxiv_id": "2405.12345",
      "title": "Paper Title",
      "authors": ["Author 1", "Author 2"],
      "abstract": "...",
      "categories": ["cs.AI", "cs.CL"],
      "published_date": "2026-05-15T00:00:00",
      "pdf_url": "https://arxiv.org/pdf/2405.12345",
      "ai_summary": "AI generated summary...",
      "ai_summary_zh": "AI生成的摘要...",
      "key_findings": ["Finding 1", "Finding 2"],
      "relevance_score": 0.85,
      "is_downloaded": true,
      "is_read": false,
      "is_bookmarked": false,
      "created_at": "2026-05-15T08:00:00"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

#### 获取单篇论文

```http
GET /api/v1/papers/{paper_id}
```

#### 标记为已读

```http
PUT /api/v1/papers/{paper_id}/read
```

#### 切换收藏状态

```http
PUT /api/v1/papers/{paper_id}/bookmark
```

**响应：**

```json
{
  "message": "Bookmark toggled",
  "is_bookmarked": true
}
```

#### 设置相关性

```http
PUT /api/v1/papers/{paper_id}/relevance?is_relevant=true
```

#### 搜索论文

```http
POST /api/v1/papers/search?query=machine+learning&k=10
```

**响应：**

```json
{
  "results": [
    {
      "arxiv_id": "2405.12345",
      "title": "Relevant Paper",
      "score": 0.92,
      "snippet": "First 200 characters..."
    }
  ],
  "query": "machine learning"
}
```

### Interests API

#### 获取兴趣列表

```http
GET /api/v1/interests?active_only=true
```

#### 创建兴趣

```http
POST /api/v1/interests
```

**请求体：**

```json
{
  "topic": "Large Language Models",
  "description": "Research on LLMs",
  "keywords": ["LLM", "transformer", "GPT"],
  "categories": ["cs.CL", "cs.AI"],
  "weight": 1.5
}
```

#### 更新兴趣

```http
PUT /api/v1/interests/{interest_id}
```

#### 删除兴趣

```http
DELETE /api/v1/interests/{interest_id}
```

### Recommendations API

#### 获取推荐列表

```http
GET /api/v1/recommendations?page=1&page_size=20&min_score=0.6
```

#### 获取今日推荐

```http
GET /api/v1/recommendations/today
```

**响应：**

```json
{
  "recommendations": [
    {
      "id": 1,
      "paper": { ... },
      "score": 0.95,
      "reason": "Matches your interest in LLMs",
      "is_viewed": false,
      "recommended_at": "2026-05-15T08:00:00"
    }
  ],
  "count": 10,
  "date": "2026-05-15T00:00:00"
}
```

#### 获取每日摘要

```http
GET /api/v1/recommendations/digest
```

**响应：**

```json
{
  "digest": "📰 Daily Research Digest...",
  "papers": [ ... ],
  "date": "2026-05-15T00:00:00"
}
```

#### 刷新推荐

```http
POST /api/v1/recommendations/refresh
```

**响应：**

```json
{
  "message": "Recommendations refreshed",
  "papers_found": 50,
  "papers_relevant": 15,
  "recommendations": 10,
  "digest": "..."
}
```

#### 标记为已查看

```http
PUT /api/v1/recommendations/{rec_id}/viewed
```

#### 忽略推荐

```http
PUT /api/v1/recommendations/{rec_id}/dismiss
```

### Conversations API

#### 提问

```http
POST /api/v1/conversations/ask
```

**请求体：**

```json
{
  "paper_id": 1,
  "question": "What is the main contribution?",
  "conversation_history": [
    {"role": "user", "content": "Previous question"},
    {"role": "assistant", "content": "Previous answer"}
  ]
}
```

**响应：**

```json
{
  "response": "The main contribution is...",
  "sources": ["Paper: Paper Title"],
  "paper": {
    "id": 1,
    "title": "Paper Title",
    "arxiv_id": "2405.12345"
  }
}
```

#### 获取对话历史

```http
GET /api/v1/conversations/{paper_id}
```

**响应：**

```json
[
  {
    "id": 1,
    "paper_id": 1,
    "user_message": "What is the main contribution?",
    "ai_response": "The main contribution is...",
    "created_at": "2026-05-15T10:30:00"
  }
]
```

#### 删除对话

```http
DELETE /api/v1/conversations/{conversation_id}
```

### System API

#### 获取系统统计

```http
GET /api/v1/system/stats
```

**响应：**

```json
{
  "total_papers": 150,
  "total_interests": 5,
  "total_recommendations": 50,
  "unread_papers": 30,
  "bookmarked_papers": 10,
  "last_fetch": "2026-05-15T08:00:00"
}
```

#### 手动触发抓取

```http
POST /api/v1/system/fetch
```

**响应：**

```json
{
  "status": "success",
  "papers_found": 50,
  "papers_relevant": 15,
  "papers_downloaded": 12,
  "digest": "..."
}
```

#### 获取抓取日志

```http
GET /api/v1/system/fetch-logs?limit=10
```

**响应：**

```json
[
  {
    "id": 1,
    "fetch_date": "2026-05-15T08:00:00",
    "papers_found": 50,
    "papers_relevant": 15,
    "papers_downloaded": 12,
    "status": "success",
    "error_message": null
  }
]
```

#### 健康检查

```http
GET /api/v1/system/health
```

**响应：**

```json
{
  "status": "healthy",
  "timestamp": "2026-05-15T10:30:00",
  "version": "0.1.0"
}
```

---

## 架构设计

### LangGraph工作流详解

#### Paper Agent工作流

Paper Agent负责论文的获取、分析和推荐：

```python
# 工作流节点
1. fetch_papers    - 从arXiv获取论文
2. analyze_papers  - 使用LLM生成摘要和分析
3. filter_relevant - 基于兴趣筛选相关论文
4. generate_recommendations - 生成推荐列表
5. create_digest   - 创建每日研究摘要
6. save_to_database - 保存到数据库和向量存储
```

#### QA Agent工作流

QA Agent负责论文问答：

```python
# 工作流节点
1. retrieve_context - 从向量存储检索相关上下文
2. generate_response - 使用LLM生成回答
3. save_conversation - 保存对话历史
```

### RAG系统设计

#### 文档处理流程

```
PDF文件
    │
    ▼
┌──────────────┐
│  提取文本    │  PyMuPDF
└──────────────┘
    │
    ▼
┌──────────────┐
│  文本分块    │  1000字符/块，200字符重叠
└──────────────┘
    │
    ▼
┌──────────────┐
│  生成嵌入    │  all-MiniLM-L6-v2
└──────────────┘
    │
    ▼
┌──────────────┐
│  存储向量    │  ChromaDB
└──────────────┘
```

#### 检索流程

```
用户问题
    │
    ▼
┌──────────────┐
│  问题嵌入    │  all-MiniLM-L6-v2
└──────────────┘
    │
    ▼
┌──────────────┐
│  向量搜索    │  ChromaDB相似度搜索
└──────────────┘
    │
    ▼
┌──────────────┐
│  获取Top-K   │  返回最相关的5个块
└──────────────┘
    │
    ▼
┌──────────────┐
│  构建提示    │  组合问题和上下文
└──────────────┘
    │
    ▼
┌──────────────┐
│  生成回答    │  GPT-4o-mini
└──────────────┘
```

### 数据模型

#### Paper（论文）

```python
class Paper:
    id: int                    # 主键
    arxiv_id: str              # arXiv ID（唯一）
    title: str                 # 标题
    authors: list[str]         # 作者列表
    abstract: str              # 摘要
    categories: list[str]      # arXiv类别
    published_date: datetime   # 发表日期
    updated_date: datetime     # 更新日期
    pdf_url: str               # PDF链接
    local_pdf_path: str        # 本地PDF路径

    # AI生成内容
    ai_summary: str            # 英文摘要
    ai_summary_zh: str         # 中文摘要
    key_findings: list[str]    # 关键发现
    relevance_score: float     # 相关性评分

    # 状态
    is_downloaded: bool        # 是否已下载
    is_relevant: bool          # 用户反馈：是否相关
    is_read: bool              # 是否已读
    is_bookmarked: bool        # 是否收藏
```

#### UserInterest（用户兴趣）

```python
class UserInterest:
    id: int                    # 主键
    topic: str                 # 研究主题
    description: str           # 详细描述
    keywords: list[str]        # 关键词列表
    categories: list[str]      # 偏好的arXiv类别
    weight: float              # 重要性权重（0.1-2.0）
    is_active: bool            # 是否启用
```

#### PaperRecommendation（推荐记录）

```python
class PaperRecommendation:
    id: int                    # 主键
    paper_id: int              # 关联论文ID
    interest_id: int           # 关联兴趣ID
    score: float               # 推荐评分（0-1）
    reason: str                # 推荐原因
    is_viewed: bool            # 是否已查看
    is_dismissed: bool         # 是否已忽略
    recommended_at: datetime   # 推荐时间
```

#### Conversation（对话记录）

```python
class Conversation:
    id: int                    # 主键
    paper_id: int              # 关联论文ID
    user_message: str          # 用户消息
    ai_response: str           # AI回答
    context_used: str          # 使用的RAG上下文
    created_at: datetime       # 创建时间
```

---

## 开发指南

### 项目结构

```
arxiv-tracker-agent/
├── backend/                    # 后端代码
│   ├── agents/                # LangGraph Agents
│   │   ├── __init__.py
│   │   ├── paper_agent.py     # 论文处理Agent
│   │   └── qa_agent.py        # 问答Agent
│   ├── api/                   # API路由
│   │   ├── __init__.py
│   │   ├── conversations.py   # 对话API
│   │   ├── interests.py       # 兴趣API
│   │   ├── papers.py          # 论文API
│   │   ├── recommendations.py # 推荐API
│   │   └── system.py          # 系统API
│   ├── core/                  # 核心配置
│   │   ├── __init__.py
│   │   └── config.py          # 配置管理
│   ├── models/                # 数据模型
│   │   ├── __init__.py
│   │   └── database.py        # 数据库模型
│   ├── services/              # 业务服务
│   │   ├── __init__.py
│   │   ├── arxiv_service.py   # arXiv API服务
│   │   ├── llm_service.py     # LLM服务
│   │   ├── pdf_service.py     # PDF处理服务
│   │   ├── rag_service.py     # RAG服务
│   │   └── vector_store.py    # 向量存储服务
│   ├── __init__.py
│   ├── main.py                # FastAPI应用入口
│   └── scheduler.py           # 定时任务调度
├── frontend/                  # 前端代码
│   ├── src/
│   │   ├── app/               # 页面组件
│   │   │   ├── page.tsx       # 首页
│   │   │   ├── papers/        # 论文页面
│   │   │   ├── recommendations/ # 推荐页面
│   │   │   ├── interests/     # 兴趣页面
│   │   │   └── settings/      # 设置页面
│   │   ├── components/        # 通用组件
│   │   │   └── Layout.tsx     # 布局组件
│   │   ├── services/          # API服务
│   │   │   └── api.ts         # API客户端
│   │   ├── types/             # TypeScript类型
│   │   │   └── index.ts       # 类型定义
│   │   ├── App.tsx            # 应用入口
│   │   ├── main.tsx           # 主入口
│   │   └── index.css          # 全局样式
│   ├── index.html             # HTML模板
│   ├── package.json           # 依赖配置
│   ├── tsconfig.json          # TypeScript配置
│   ├── vite.config.ts         # Vite配置
│   ├── tailwind.config.js     # Tailwind配置
│   └── postcss.config.js      # PostCSS配置
├── config/                    # 配置文件
├── data/                      # 数据目录
│   ├── papers/                # 下载的PDF文件
│   └── vectors/               # ChromaDB数据
├── .env.example               # 环境变量示例
├── .gitignore                 # Git忽略文件
├── docker-compose.yml         # Docker配置
├── Dockerfile.backend         # 后端Dockerfile
├── pyproject.toml             # Python项目配置
├── README.md                  # 项目文档
└── start.sh                   # 启动脚本
```

### 添加新功能

#### 1. 添加新的API端点

```python
# backend/api/papers.py
@router.post("/new-endpoint")
async def new_endpoint(request: RequestModel):
    # 实现逻辑
    return {"result": "data"}
```

#### 2. 添加新的Agent节点

```python
# backend/agents/paper_agent.py
async def new_node(state: PaperState) -> PaperState:
    """新节点的实现"""
    # 处理逻辑
    return {**state, "new_field": result}

# 添加到工作流
workflow.add_node("new_node", new_node)
workflow.add_edge("previous_node", "new_node")
```

#### 3. 添加新的服务

```python
# backend/services/new_service.py
class NewService:
    def __init__(self):
        # 初始化
        pass

    async def new_method(self):
        # 实现
        pass

# 单例模式
_new_service = None

def get_new_service() -> NewService:
    global _new_service
    if _new_service is None:
        _new_service = NewService()
    return _new_service
```

#### 4. 添加新的前端页面

```tsx
// frontend/src/app/new-page/page.tsx
export default function NewPage() {
  const [data, setData] = useState(null)

  useEffect(() => {
    // 加载数据
  }, [])

  return (
    <div>
      <h1>New Page</h1>
      {/* 页面内容 */}
    </div>
  )
}
```

### 代码规范

#### Python

- 使用Black格式化代码
- 使用isort排序导入
- 使用mypy进行类型检查

```bash
# 格式化代码
black backend/

# 排序导入
isort backend/

# 类型检查
mypy backend/
```

#### TypeScript/React

- 使用ESLint检查代码
- 使用Prettier格式化

```bash
cd frontend

# 检查代码
npm run lint

# 格式化
npm run format
```

### 测试

#### 运行后端测试

```bash
# 安装测试依赖
uv pip install -e ".[dev]"

# 运行测试
pytest backend/tests/
```

#### 运行前端测试

```bash
cd frontend

# 运行测试
npm test

# 运行测试并生成覆盖率报告
npm test -- --coverage
```

---

## 部署指南

### 生产环境配置

#### 1. 环境变量

```env
# 关闭调试模式
DEBUG=false

# 使用生产数据库
DATABASE_URL=postgresql://user:password@localhost/arxiv_tracker

# 设置密钥
SECRET_KEY=your-secret-key-here

# 配置CORS
CORS_ORIGINS=https://yourdomain.com
```

#### 2. 使用Gunicorn

```bash
# 安装Gunicorn
uv pip install gunicorn

# 启动
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

#### 3. 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker部署

#### 构建镜像

```bash
# 构建后端
docker build -t arxiv-tracker-backend -f Dockerfile.backend .

# 构建前端
docker build -t arxiv-tracker-frontend ./frontend
```

#### 使用Docker Compose

```bash
# 启动所有服务
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 云部署

#### AWS

1. 使用EC2实例
2. 配置安全组
3. 使用RDS作为数据库
4. 使用S3存储PDF文件

#### Google Cloud

1. 使用Cloud Run
2. 使用Cloud SQL
3. 使用Cloud Storage

#### Vercel + Railway

1. 前端部署到Vercel
2. 后端部署到Railway
3. 使用环境变量配置

---

## 故障排除

### 常见问题

#### 1. OpenAI API错误

**问题：** `AuthenticationError: Incorrect API key`

**解决：**
- 检查 `.env` 文件中的 `OPENAI_API_KEY`
- 确保API密钥有效且有足够额度

#### 2. 数据库错误

**问题：** `OperationalError: unable to open database`

**解决：**
- 确保 `data/` 目录存在
- 检查文件权限
- 删除 `data/arxiv_tracker.db` 重新初始化

#### 3. ChromaDB错误

**问题：** `Failed to initialize ChromaDB`

**解决：**
- 删除 `data/vectors/` 目录
- 重新启动应用

#### 4. 前端无法连接后端

**问题：** `Network Error` 或 `CORS Error`

**解决：**
- 确保后端正在运行
- 检查 `vite.config.ts` 中的代理配置
- 检查后端CORS配置

#### 5. 论文抓取失败

**问题：** `Failed to fetch papers`

**解决：**
- 检查网络连接
- 确保arXiv API可访问
- 检查日志获取详细错误信息

### 查看日志

#### 后端日志

```bash
# 实时查看日志
tail -f logs/backend.log

# 或使用Docker
docker-compose logs -f backend
```

#### 前端日志

- 打开浏览器开发者工具（F12）
- 查看Console标签

### 重置数据

```bash
# 删除所有数据
rm -rf data/

# 重新初始化
mkdir -p data/papers data/vectors
uv run uvicorn backend.main:app
```

---

## 贡献指南

### 如何贡献

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

### 开发流程

1. 克隆你的Fork
2. 创建开发分支
3. 安装开发依赖
4. 进行开发
5. 编写测试
6. 提交PR

### 代码审查

- 确保代码通过所有测试
- 确保代码符合项目规范
- 添加必要的文档
- 更新README（如果需要）

### 报告问题

使用GitHub Issues报告问题，包含：
- 问题描述
- 复现步骤
- 期望行为
- 实际行为
- 环境信息

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 致谢

- [LangChain](https://langchain.com/) - LLM应用框架
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent工作流引擎
- [FastAPI](https://fastapi.tiangolo.com/) - Web框架
- [ChromaDB](https://www.trychroma.com/) - 向量数据库
- [arXiv](https://arxiv.org/) - 论文预印本平台
- [sentence-transformers](https://www.sbert.net/) - 文本嵌入模型

---

## 联系方式

- 项目链接: [GitHub Repository](https://github.com/yourusername/arxiv-tracker-agent)
- 问题反馈: [GitHub Issues](https://github.com/yourusername/arxiv-tracker-agent/issues)

---

<div align="center">

**如果这个项目对你有帮助，请给一个Star！**

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/arxiv-tracker-agent&type=Date)](https://star-history.com/#yourusername/arxiv-tracker-agent&Date)

</div>
