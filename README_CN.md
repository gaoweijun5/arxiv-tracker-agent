# ArXiv 论文追踪 Agent

> **如果这个项目对你有帮助，请给一个 ⭐ Star！你的支持是我持续改进的动力。**

基于 LangChain、LangGraph ReAct Agent 构建的 AI 论文追踪与智能推荐系统。

https://github.com/user-attachments/assets/880cb912-5e25-4a0f-b684-710d7716dbaf

[English](README.md) | 中文

## 功能特性

- **自主论文 Agent** - ReAct Agent 自主决定搜索策略、分析论文、保存最优结果
- **智能论文发现** - 根据研究兴趣搜索 arXiv，支持自定义日期范围
- **AI 摘要生成** - 使用 DeepSeek 生成论文摘要、关键发现和中文翻译
- **语义推荐** - 基于 DashScope 向量嵌入的论文匹配推荐
- **全文问答** - 基于论文完整 PDF 内容的问答，而非分块检索
- **实时进度** - WebSocket 驱动的论文抓取实时进度显示
- **论文管理** - 收藏、标记已读、筛选、批量删除论文
- **LangSmith 可观测性** - Agent 决策和 LLM 调用的完整追踪

## 技术栈

| 组件 | 技术 |
|------|------|
| **后端** | Python, FastAPI, LangChain, LangGraph |
| **LLM** | DeepSeek v4 Flash |
| **向量嵌入** | DashScope text-embedding-v4 |
| **向量数据库** | ChromaDB |
| **关系数据库** | SQLite + SQLAlchemy |
| **前端** | React, TypeScript, Tailwind CSS |
| **可观测性** | LangSmith |
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

# LangSmith 追踪（可选）
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=your-project-name
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
- Agent 自动搜索、分析、筛选并保存高质量论文
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
- 针对论文内容提问
- AI 读取完整 PDF 全文进行回答
- 对话历史自动保存
- 点击垃圾桶图标清空聊天记录

## API 接口

### 论文接口
- `GET /api/v1/papers` - 获取论文列表（支持筛选和排序）
- `GET /api/v1/papers/{id}` - 获取论文详情
- `DELETE /api/v1/papers/{id}` - 删除论文
- `POST /api/v1/papers/batch-delete` - 批量删除论文
- `PUT /api/v1/papers/{id}/read` - 标记已读
- `PUT /api/v1/papers/{id}/bookmark` - 切换收藏
- `POST /api/v1/papers/{id}/download` - 下载 PDF 用于问答
- `POST /api/v1/papers/search` - 语义搜索

### 对话接口
- `POST /api/v1/conversations/ask` - 针对论文提问
- `GET /api/v1/conversations/{paper_id}` - 获取对话历史
- `DELETE /api/v1/conversations/paper/{paper_id}` - 清空聊天记录

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
- `GET /api/v1/system/fetch-logs` - 抓取历史（含来源：手动/自动）
- `GET /api/v1/system/scheduler` - 获取定时任务配置
- `PUT /api/v1/system/scheduler` - 更新定时任务配置

### WebSocket
- `ws://localhost:8000/ws/progress/{task_id}` - 实时进度

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
│  LangGraph    │ │   Services    │ │   Database    │
│               │ │               │ │               │
│ - Paper Agent │ │ - arXiv API   │ │ - SQLite      │
│ - QA Agent    │ │ - DeepSeek    │ │ - ChromaDB    │
│ (ReAct)       │ │ - DashScope   │ │               │
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
│  7. download_and_save_paper() → 保存最优     │
│                                              │
│  LLM 自主决定工具调用顺序                     │
│  根据结果调整策略（反思）                      │
└─────────────────────────────────────────────┘
```

## 许可证

MIT
